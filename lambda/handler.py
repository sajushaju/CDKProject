# import json
# import os
# import boto3
# import pg8000.native

# def get_secrets():
#     secret_name = os.environ['DB_SECRET_ARN']
#     region_name = os.environ.get('AWS_REGION', 'eu-central-1')
#     client = boto3.client('secretsmanager', region_name=region_name)
    
#     response = client.get_secret_value(SecretId=secret_name)
#     return json.loads(response['SecretString'])

# def main(event, context):
#     try:
#         # Get credentials from Secrets Manager
#         creds = get_secrets()
        
#         # Connect to Database
#         conn = pg8000.native.Connection(
#             user=creds['username'],
#             password=creds['password'],
#             host=creds['host'],
#             port=int(creds['port']),
#             database=os.environ['DB_NAME'],
#             timeout=10 # Stop waiting after 10 seconds
#         )

#         # Create table if it doesn't exist
#         conn.run("CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, name TEXT);")

#         method = event.get('httpMethod')
        
#         if method == 'POST':
#             body = json.loads(event.get('body', '{}'))
#             conn.run("INSERT INTO items (id, name) VALUES (:id, :name) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name", 
#                      id=body.get('id'), name=body.get('name'))
#             return {
#                 'statusCode': 201,
#                 'body': json.dumps({'message': 'Item saved successfully!'})
#             }

#         elif method == 'GET':
#             rows = conn.run("SELECT id, name FROM items")
#             items = [{'id': row[0], 'name': row[1]} for row in rows]
#             return {
#                 'statusCode': 200,
#                 'body': json.dumps(items)
#             }

#     except Exception as e:
#         # This will send the REAL error to Postman so we can see it!
#         return {
#             'statusCode': 500,
#             'body': json.dumps({'error': str(e)})
#         }
#     finally:
#         if 'conn' in locals():
#             conn.close()
            
import json
import os
import boto3
import pg8000.native

def get_secrets():
    secret_name = os.environ['DB_SECRET_ARN']
    region_name = os.environ.get('AWS_REGION', 'eu-central-1')
    client = boto3.client('secretsmanager', region_name=region_name)
    
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

def main(event, context):
    try:
        creds = get_secrets()
        
        conn = pg8000.native.Connection(
            user=creds['username'],
            password=creds['password'],
            host=creds['host'],
            port=int(creds['port']),
            database=os.environ['DB_NAME'],
            timeout=10
        )

        # Ensure the table exists
        conn.run("CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, name TEXT);")

        method = event.get('httpMethod')
        
        # This captures the ID from the URL (e.g., /items/1)
        path_params = event.get('pathParameters') or {}
        item_id = path_params.get('proxy') 

        # --- GET (List All or Fetch One) ---
        if method == 'GET':
            if item_id:
                # Fetch a single item by ID
                rows = conn.run("SELECT id, name FROM items WHERE id = :id", id=item_id)
                if not rows:
                    return {'statusCode': 404, 'body': json.dumps({'error': 'Item not found'})}
                return {'statusCode': 200, 'body': json.dumps({'id': rows[0][0], 'name': rows[0][1]})}
            
            # List all items
            rows = conn.run("SELECT id, name FROM items")
            items_list = [{'id': row[0], 'name': row[1]} for row in rows]
            return {'statusCode': 200, 'body': json.dumps(items_list)}

        # --- POST (Create or Replace) ---
        elif method == 'POST':
            body = json.loads(event.get('body', '{}'))
            conn.run("INSERT INTO items (id, name) VALUES (:id, :name) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name", 
                     id=body.get('id'), name=body.get('name'))
            return {
                'statusCode': 201, 
                'body': json.dumps({'message': 'Item saved successfully!'})
            }

        # --- PUT (Update existing name) ---
        elif method == 'PUT':
            if not item_id:
                return {'statusCode': 400, 'body': json.dumps({'error': 'Item ID is required in URL'})}
            
            body = json.loads(event.get('body', '{}'))
            conn.run("UPDATE items SET name = :name WHERE id = :id", name=body.get('name'), id=item_id)
            return {'statusCode': 200, 'body': json.dumps({'message': f'Item {item_id} updated'})}

        # --- DELETE (Remove item) ---
        elif method == 'DELETE':
            if not item_id:
                return {'statusCode': 400, 'body': json.dumps({'error': 'Item ID is required in URL'})}
            
            conn.run("DELETE FROM items WHERE id = :id", id=item_id)
            return {'statusCode': 200, 'body': json.dumps({'message': f'Item {item_id} deleted'})}

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
    finally:
        if 'conn' in locals():
            conn.close()