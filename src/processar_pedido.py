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
