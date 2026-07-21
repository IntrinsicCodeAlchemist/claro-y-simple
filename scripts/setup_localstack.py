"""Crea los recursos AWS en LocalStack usando boto3 directamente.
Equivalente a setup-localstack.sh pero sin dependencia de aws CLI."""
import os
import sys
sys.path.insert(0, r"C:\Users\javier.salas.blanco\Projects\hackathon-draft\backend")

from shared.aws_utils import get_boto3_client

ENDPOINT = "http://localhost:4566"
REGION = "us-east-1"
S3_BUCKET = "claro-y-simple-contracts"
TABLE_EXTRACTIONS = "ContractExtractions"
TABLE_ANALYSES = "ContractAnalyses"

os.environ["AWS_ENDPOINT_URL"] = ENDPOINT
os.environ["AWS_DEFAULT_REGION"] = REGION
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

s3 = get_boto3_client("s3")
dynamo = get_boto3_client("dynamodb")

# --- S3 bucket ---
try:
    s3.head_bucket(Bucket=S3_BUCKET)
    print(f"Bucket '{S3_BUCKET}' already exists")
except Exception:
    s3.create_bucket(Bucket=S3_BUCKET)
    print(f"Created S3 bucket: {S3_BUCKET}")

# Lifecycle policy
s3.put_bucket_lifecycle_configuration(
    Bucket=S3_BUCKET,
    LifecycleConfiguration={
        "Rules": [{
            "ID": "expire-contracts-24h",
            "Status": "Enabled",
            "Filter": {"Prefix": "contracts/"},
            "Expiration": {"Days": 1},
        }]
    },
)
print("Lifecycle policy applied.")

# --- DynamoDB tables ---
for table_name in (TABLE_EXTRACTIONS, TABLE_ANALYSES):
    try:
        dynamo.describe_table(TableName=table_name)
        print(f"Table '{table_name}' already exists")
    except dynamo.exceptions.ResourceNotFoundException:
        dynamo.create_table(
            TableName=table_name,
            AttributeDefinitions=[{"AttributeName": "document_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "document_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"Created DynamoDB table: {table_name}")

    dynamo.update_time_to_live(
        TableName=table_name,
        TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
    )
    print(f"TTL enabled on '{table_name}'")

print("\nLocalStack bootstrap complete!")
