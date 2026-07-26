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
