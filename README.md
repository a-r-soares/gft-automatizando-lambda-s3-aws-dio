## DIO - Bootcamp GFT - Fundamentos de Cloud com AWS

<br>

## Desafio -  Tarefas Automatizadas com Lambda Function e S3

### AWS Local — Processamento de Pedidos (S3 + Lambda + DynamoDB + API Gateway)

Mini-projeto prático para simular, localmente via **LocalStack**, um fluxo real de processamento de pedidos na AWS: upload de arquivo, processamento automático via Lambda, persistência em banco NoSQL e exposição via API REST para consulta.

## 🏗️ Arquitetura

```
Usuário → upload pedido.json → S3 (bucket "pedidos")
                                      │
                                      │ trigger (s3:ObjectCreated)
                                      ▼
                          Lambda "processar-pedido"
                                      │
                                      ▼
                          DynamoDB (tabela "Pedidos")
                                      ▲
                                      │ consulta
                          Lambda "consultar-pedido"
                                      ▲
                                      │ GET /pedidos/{id}
                              API Gateway (stage: dev)
                                      ▲
                                      │
                                  Postman / curl
```

## 🧰 Componentes utilizados

| Componente | Função |
|---|---|
| **Amazon S3** | Armazenamento do arquivo de pedido recebido |
| **AWS Lambda** | Processamento do arquivo (gravação) e consulta de pedidos |
| **Amazon DynamoDB** | Armazenamento dos dados extraídos do pedido |
| **IAM** | Papel de execução das Lambdas (`lambda-role`) |
| **API Gateway** | Exposição do endpoint REST `GET /pedidos/{id}` |

## ⚙️ Ambiente

- **Windows 11** + **WSL2** (Ubuntu)
- **Docker Desktop** com integração WSL2
- **Python 3** em ambiente virtual (`venv`)
- **LocalStack CLI** (conta Hobby/free, com Auth Token configurado)
- **awscli-local** (`awslocal`) para simplificar as chamadas à AWS local

### Setup do ambiente

```bash
# WSL2 + Docker Desktop já configurados previamente

# Ambiente virtual Python
python3 -m venv ~/venv-aws
source ~/venv-aws/bin/activate

# Dependências
pip install localstack awscli-local awscli

# Autenticação LocalStack (conta gratuita Hobby)
# Obtenha seu token gratuito em https://app.localstack.cloud
localstack auth set-token <SEU_TOKEN_AQUI>

# Subir o LocalStack
localstack start -d
localstack status
```

## 📦 Passo a passo da implementação

### 1. Bucket S3
```bash
awslocal s3 mb s3://pedidos
```

### 2. Tabela DynamoDB
```bash
awslocal dynamodb create-table \
  --table-name Pedidos \
  --attribute-definitions AttributeName=pedido_id,AttributeType=S \
  --key-schema AttributeName=pedido_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

### 3. Lambda "processar-pedido"

```python
import json
import os
import boto3
import urllib.parse

LOCALSTACK_HOSTNAME = os.environ.get('LOCALSTACK_HOSTNAME', 'localhost')
ENDPOINT_URL = f'http://{LOCALSTACK_HOSTNAME}:4566'

s3 = boto3.client('s3', endpoint_url=ENDPOINT_URL)
dynamodb = boto3.resource('dynamodb', endpoint_url=ENDPOINT_URL)
table = dynamodb.Table('Pedidos')

def handler(event, context):
    record = event['Records'][0]
    bucket = record['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(record['s3']['object']['key'])

    obj = s3.get_object(Bucket=bucket, Key=key)
    pedido = json.loads(obj['Body'].read())

    pedido['status'] = 'RECEBIDO'
    table.put_item(Item=pedido)

    return {'statusCode': 200, 'body': f"Pedido {pedido['pedido_id']} gravado"}
```

```bash
zip processar-pedido.zip processar_pedido.py

awslocal lambda create-function \
  --function-name processar-pedido \
  --runtime python3.12 \
  --handler processar_pedido.handler \
  --zip-file fileb://processar-pedido.zip \
  --role arn:aws:iam::000000000000:role/lambda-role
```

### 4. Conectar o gatilho S3 → Lambda

```bash
awslocal lambda add-permission \
  --function-name processar-pedido \
  --statement-id s3invoke \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::pedidos
```

`notification.json`:
```json
{
  "LambdaFunctionConfigurations": [
    {
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:000000000000:function:processar-pedido",
      "Events": ["s3:ObjectCreated:*"]
    }
  ]
}
```

```bash
awslocal s3api put-bucket-notification-configuration \
  --bucket pedidos \
  --notification-configuration file://notification.json
```

### 5. Lambda "consultar-pedido"

```python
import json
import os
import boto3

LOCALSTACK_HOSTNAME = os.environ.get('LOCALSTACK_HOSTNAME', 'localhost')
ENDPOINT_URL = f'http://{LOCALSTACK_HOSTNAME}:4566'

dynamodb = boto3.resource('dynamodb', endpoint_url=ENDPOINT_URL)
table = dynamodb.Table('Pedidos')

def handler(event, context):
    pedido_id = event['pathParameters']['id']
    resp = table.get_item(Key={'pedido_id': pedido_id})

    if 'Item' not in resp:
        return {'statusCode': 404, 'body': json.dumps({'erro': 'Pedido não encontrado'})}

    return {'statusCode': 200, 'body': json.dumps(resp['Item'])}
```

```bash
zip consultar-pedido.zip consultar_pedido.py

awslocal lambda create-function \
  --function-name consultar-pedido \
  --runtime python3.12 \
  --handler consultar_pedido.handler \
  --zip-file fileb://consultar-pedido.zip \
  --role arn:aws:iam::000000000000:role/lambda-role
```

### 6. API Gateway

```bash
# Criar a API
awslocal apigateway create-rest-api --name "PedidosAPI"
# → retorna { id: <API_ID>, rootResourceId: <ROOT_ID> }

# Recurso /pedidos
awslocal apigateway create-resource \
  --rest-api-id <API_ID> \
  --parent-id <ROOT_ID> \
  --path-part pedidos

# Recurso /pedidos/{id}
awslocal apigateway create-resource \
  --rest-api-id <API_ID> \
  --parent-id <ID_DO_/pedidos> \
  --path-part "{id}"

# Método GET
awslocal apigateway put-method \
  --rest-api-id <API_ID> \
  --resource-id <ID_DO_/pedidos/{id}> \
  --http-method GET \
  --authorization-type NONE

# Integração com a Lambda (AWS_PROXY)
awslocal apigateway put-integration \
  --rest-api-id <API_ID> \
  --resource-id <ID_DO_/pedidos/{id}> \
  --http-method GET \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:000000000000:function:consultar-pedido/invocations

# Permissão do API Gateway invocar a Lambda
awslocal lambda add-permission \
  --function-name consultar-pedido \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:000000000000:<API_ID>/*/GET/pedidos/*"

# Deploy no stage "dev"
awslocal apigateway create-deployment \
  --rest-api-id <API_ID> \
  --stage-name dev
```

## ✅ Testes realizados

**Upload do pedido (dispara o fluxo S3 → Lambda → DynamoDB):**
```bash
echo '{"pedido_id": "001", "cliente": "Roberto", "itens": ["mouse", "teclado"]}' > pedido.json
awslocal s3 cp pedido.json s3://pedidos/pedido.json
```

**Confirmação no DynamoDB:**
```json
{
  "Items": [
    {
      "cliente": {"S": "Roberto"},
      "itens": {"L": [{"S": "mouse"}, {"S": "teclado"}]},
      "pedido_id": {"S": "001"},
      "status": {"S": "RECEBIDO"}
    }
  ],
  "Count": 1
}
```

**Consulta via API (pedido existente):**
```bash
curl http://localhost:4566/restapis/<API_ID>/dev/_user_request_/pedidos/001
```
```json
{"cliente": "Roberto", "itens": ["mouse", "teclado"], "pedido_id": "001", "status": "RECEBIDO"}
```

**Consulta via API (pedido inexistente — tratamento de erro):**
```bash
curl -i http://localhost:4566/restapis/<API_ID>/dev/_user_request_/pedidos/999
```
```
HTTP/1.1 404 NOT FOUND
{"erro": "Pedido não encontrado"}
```

## 🐛 Troubleshooting — problema real enfrentado

**Sintoma:** upload no S3 funcionava, mas o item nunca aparecia no DynamoDB. Logs da Lambda mostravam `Status: timeout` sem nenhum erro de Python.

**Causa:** o código usava `endpoint_url='http://localhost:4566'` fixo. Dentro do container onde a Lambda executa, `localhost` aponta para o **próprio container da Lambda**, não para o container do LocalStack — por isso a chamada nunca completava e estourava o timeout de 3s.

**Solução:** o LocalStack injeta automaticamente a variável de ambiente `LOCALSTACK_HOSTNAME` dentro do container da Lambda, apontando para o host correto. Ajuste aplicado:

```python
LOCALSTACK_HOSTNAME = os.environ.get('LOCALSTACK_HOSTNAME', 'localhost')
ENDPOINT_URL = f'http://{LOCALSTACK_HOSTNAME}:4566'
```

Depois de atualizar o código (`aws lambda update-function-code`) e reenviar o arquivo, o fluxo funcionou corretamente.

## 📚 Aprendizados

- Diferença entre rodar comandos "de fora" (terminal, via `awslocal`) e "de dentro" (código da Lambda, que roda em outro container)
- Configuração de triggers S3 → Lambda via `put-bucket-notification-configuration`
- Estrutura em camadas do API Gateway (API → Resource → Method → Integration → Deployment)
- Debug de Lambda via CloudWatch Logs (`describe-log-groups`, `describe-log-streams`, `get-log-events`)
- Necessidade de conta (LocalStack Hobby, gratuita) para uso do LocalStack desde 2026, mesmo em recursos community

## 🚀 Um Incentivo para a Transição de Carreira

Quem vem do Mainframe conhece bem o ciclo clássico: um arquivo cai numa fila, um job batch processa milhares de registros durante a madrugada, grava o resultado numa base e, no dia seguinte, alguém consulta o que foi processado. Esse desafio é, no fundo, a mesma lógica — só que reescrita com o dicionário da nuvem: o arquivo que cai é um objeto no **S3**, o job batch vira uma **Lambda** disparada por evento, a base de gravação é o **DynamoDB**, e a consulta do dia seguinte agora acontece na hora, via **API Gateway**.

A diferença real não está no *conceito*, está na *velocidade e no gatilho*: o Mainframe processa em lote, em horários programados; a nuvem processa em evento, no instante em que algo acontece. Mas separar dados de entrada, lógica de processamento, persistência e consulta — isso quem trabalhou com JCL, COBOL e CICS já faz há décadas, muitas vezes com uma disciplina de tratamento de erro e integridade de dados que boa parte do mundo cloud-native ainda está aprendendo.

O erro do `LOCALSTACK_HOSTNAME` enfrentado neste desafio é um bom exemplo disso: não foi resolvido por sorte, foi resolvido lendo o log, isolando a causa e testando a hipótese — exatamente o raciocínio de quem já debugou um `S0C7` ou uma abend em produção. Essa bagagem não fica pra trás numa transição de carreira; ela é a base sobre a qual as ferramentas novas são só um vocabulário a mais para aprender.



---

### <img width="20" height="20" alt="image" src="https://github.com/user-attachments/assets/3f883ffa-dbfb-43d7-ae40-bd9456d6440f" /> Agradecimentos

[Equipe GFT](https://www.gft.com/br/pt)

[Equipe DIO](https://www.dio.me)

Utilização de IA principalmente para tornar a documentação mais clara, objetiva e fluída.

Brasil, Julho de 2026
