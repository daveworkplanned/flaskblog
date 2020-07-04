import json
import psycopg2
import os
import bcrypt
import uuid
import boto3
import base64
from botocore.exceptions import ClientError
from datetime import datetime, timedelta

def retrieve_credentials():
    secret_name = "postgres-lambda-credentials"
    region_name = "us-west-2"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    # In this sample we only handle the specific exceptions for the 'GetSecretValue' API.
    # See https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
    # We rethrow the exception by default.

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'DecryptionFailureException':
            # Secrets Manager can't decrypt the protected secret text using the provided KMS key.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InternalServiceErrorException':
            # An error occurred on the server side.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            # You provided an invalid value for a parameter.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            # You provided a parameter value that is not valid for the current state of the resource.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'ResourceNotFoundException':
            # We can't find the resource that you asked for.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
    else:
        # Decrypts secret using the associated KMS CMK.
        # Depending on whether the secret is a string or binary, one of these fields will be populated.
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
            return json.loads(secret)
        else:
            decoded_binary_secret = base64.b64decode(get_secret_value_response['SecretBinary'])
            return json.loads(decoded_binary_secret)

credentials = retrieve_credentials()
db_host = credentials['host']
db_port = credentials['port']
db_name = credentials['engine']
db_user = credentials['username']
db_pass = credentials['password']
TEXT_ENCODING = 'utf-8'
TOKEN_EXPIRATION_DAYS=30

def make_conn():
    return psycopg2.connect("dbname='%s' user='%s' host='%s' password='%s'" % (db_name, db_user, db_host, db_pass))

def fetch_data(conn, query, parameters = {}):
    result = []
    print("Now executing: %s" % (query))
    cursor = conn.cursor()
    cursor.execute(query, parameters)

    raw = cursor.fetchall()
    for line in raw:
        result.append(line)

    return result

def update_data(conn, sql, record):
    print("Now executing: %s" % (sql))
    cursor = conn.cursor()
    cursor.execute(sql, record)

    conn.commit()

    return cursor.rowcount

def user_is_logged_in(event, context):
    body = event['queryStringParameters'] # query string parameters because this is a get

    error_messages = []
    if 'user_id' not in body:
        error_messages.append("user_id parameter not detected")

    if 'token' not in body:
        error_messages.append("token parameter not detected")

    if error_messages:
        return {
            'statusCode': 200,
            'body': json.dumps({'message_key': 'INVALID_REQUEST',
                                'message': ",".join(error_messages)})
        }

    user_id = body['user_id']
    token = body['token']
    earliest_last_check = datetime.now() - timedelta(days=TOKEN_EXPIRATION_DAYS)
    conn = make_conn()

    try:
        select_sql = "select * from \"user\".users inner join \"user\".login_tokens on users.user_id = login_tokens.user_id " \
              "WHERE users.user_id = %(user_id)s " \
              "AND token = %(token)s " \
              "AND is_active = true " \
              "AND login_tokens.last_checked_timestamp > %(last_checked_time)s"

        result = fetch_data(conn, select_sql, {"user_id": user_id,
                                        "token": token,
                                        "last_checked_time": earliest_last_check})

        if not result:
            return {
                'statusCode': 200,
                'body': json.dumps({'message_key': 'INVALID_TOKEN'})
            }
        else:
            update_sql = "UPDATE \"user\".login_tokens SET last_checked_timestamp = %s " \
                         "WHERE user_id = %s AND token = %s"

            update_data(conn, update_sql, (datetime.now(), user_id, token))

            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'success'}),
            }
    finally:
        conn.close()


def create_token(conn, user_id):
    login_token = str(uuid.uuid4())
    login_timestamp = datetime.now()  # let's use the server timestamp so we don't need to worry about DB time
    login_record = (user_id, login_token, login_timestamp, login_timestamp, True)
    login_create_sql = "INSERT INTO \"user\".login_tokens (user_id, " \
                                                          "token, " \
                                                          "created_timestamp, " \
                                                          "last_checked_timestamp, " \
                                                          "is_active) VALUES (%s, %s, %s, %s, %s)"

    update_data(conn, login_create_sql, login_record)

    return login_token

def user_log_in(event, context):
    body = json.loads(event['body'])

    error_messages = []
    if 'email' not in body:
        error_messages.append("email parameter not detected")

    if 'password' not in body:
        error_messages.append("password parameter not detected")

    if error_messages:
        return {
            'statusCode': 200,
            'body': json.dumps({'message_key': 'INVALID_REQUEST',
                                'message': ",".join(error_messages)})
        }

    email = body['email']
    password = body['password']

    conn = make_conn()

    try:
        result = fetch_data(conn, "select password_encryption, user_id from \"user\".users where email_address = %(email_address)s",
                            {"email_address": email})

        if not result:
            return {
                'statusCode': 200,
                'body': json.dumps({'message_key': 'SECURITY_CHECK_FAILED'})
            }

        password_encryption = result[0][0].tobytes() # only entry from first row
        if not bcrypt.checkpw(password.encode(TEXT_ENCODING), password_encryption):
            return {
                'statusCode': 200,
                'body': json.dumps({'message_key': 'SECURITY_CHECK_FAILED'})
            }

        user_id = result[0][1]

        # Success! Create a new token
        login_token = create_token(conn, user_id)

        return {
            'statusCode': 200,
            'body': json.dumps({'message_key': 'SUCCESS',
                                'token': login_token,
                                'user_id': user_id
                                })
        }
    finally:
        conn.close()

def user_sign_up(event, context):
    body = json.loads(event['body'])

    error_messages = []
    if 'email' not in body:
        error_messages.append("email parameter not detected")

    if 'password' not in body:
        error_messages.append("password parameter not detected")

    if 'first_name' not in body:
        error_messages.append("first name not detected")

    if 'last_name' not in body:
        error_messages.append("last name not detected")

    if error_messages:
        return {
            'statusCode': 200,
            'body': json.dumps({'message_key': 'INVALID_REQUEST',
                                'message': ",".join(error_messages)})
        }

    email = body['email']
    password = body['password']
    first_anme = body['first_name']
    last_name = body['last_name']

    if not email:
        error_messages.append("Email is empty")

    if not password:
        error_messages.append("Password is empty")

    if not first_anme:
        error_messages.append("First name is empty")

    if not last_name:
        error_messages.append("Last name is empty")

    if error_messages:
        return {
            'statusCode': 200,
            'body': json.dumps({'message_key': 'DATA_VALIDATION_FAILURE',
                                'message': ",".join(error_messages)})
        }

    conn = make_conn()

    try:
        result = fetch_data(conn, "select * from \"user\".users where email_address = %(email_address)s",
                            {"email_address": email})
        if result:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message_key': 'USER_ALREADY_EXISTS'
                })
            }

        rounds_of_hashing = 10 # slows things down making things more secure
        salt = bcrypt.gensalt(rounds=rounds_of_hashing)
        password_b = password.encode(TEXT_ENCODING)
        password_encryption = bcrypt.hashpw(password_b, salt)
        user_id = str(uuid.uuid4())
        user_record = (user_id, first_anme, last_name, email, password_encryption)
        user_create_sql = "INSERT INTO \"user\".users (user_id, first_name, last_name, email_address, password_encryption) " \
                          "VALUES (%s, %s, %s, %s, %s)"

        update_data(conn, user_create_sql, user_record)

        login_token = create_token(conn, user_id)

        return {
                'statusCode': 200,
                'body': json.dumps({
                    'message_key': 'SUCCESS',
                    'user_id': user_id,
                    'login_token': login_token
                })
        }
    finally:
        conn.close()

def user_log_out(event, context):
    body = event['queryStringParameters']  # query string parameters because this is a get
    # body = {}

    error_messages = []
    if 'user_id' not in body:
        error_messages.append("user_id parameter not detected")

    if 'token' not in body:
        error_messages.append("token parameter not detected")

    if error_messages:
        return {
            'statusCode': 200,
            'body': json.dumps({'message_key': 'INVALID_REQUEST',
                                'message': ",".join(error_messages),
                                'event': event})
        }

    user_id = body['user_id']
    token = body['token']

    try:
        conn = make_conn()

        update_sql = "UPDATE \"user\".login_tokens " \
              "SET is_active = false " \
              "WHERE user_id = %(user_id)s " \
              "AND token = %(token)s "

        row_count = update_data(conn, update_sql, {"user_id": user_id,
                                        "token": token})

        if row_count == 0:
            return {
                'statusCode': 200,
                'body': json.dumps({'message_key': 'INVALID_TOKEN_OR_USER_ID'})
            }
        else:
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'success'}),
            }
    finally:
        conn.close()
