import json
import os
import boto3
import base64
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

        # Tables Setup
        conn.run("CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, name TEXT);")
        conn.run("""
            CREATE TABLE IF NOT EXISTS item_profiles (
                item_id TEXT PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
                bio TEXT,
                image_url TEXT
            );
        """)

        method = event.get('httpMethod')
        path_params = event.get('pathParameters') or {}
        item_id = path_params.get('proxy') 

        # --- GET ---
        if method == 'GET':
            if item_id:
                query = """
                    SELECT i.id, i.name, p.bio, p.image_url 
                    FROM items i 
                    LEFT JOIN item_profiles p ON i.id = p.item_id 
                    WHERE i.id = :id
                """
                rows = conn.run(query, id=item_id)
                if not rows:
                    return {'statusCode': 404, 'body': json.dumps({'error': 'Not found'})}
                r = rows[0]
                return {'statusCode': 200, 'body': json.dumps({'id': r[0], 'name': r[1], 'bio': r[2], 'image_url': r[3]})}
            
            rows = conn.run("SELECT id, name FROM items")
            return {'statusCode': 200, 'body': json.dumps([{'id': r[0], 'name': r[1]} for r in rows])}

        # --- POST & PUT (Combined Logic) ---
        elif method in ['POST', 'PUT']:
            body = json.loads(event.get('body', '{}'))
            # Use ID from URL if it's a PUT, otherwise from body
            active_id = item_id if method == 'PUT' else body.get('id')
            
            if not active_id:
                return {'statusCode': 400, 'body': json.dumps({'error': 'ID is required'})}

            # 1. Update/Insert into 'items'
            if body.get('name'):
                conn.run("INSERT INTO items (id, name) VALUES (:id, :name) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name", 
                         id=active_id, name=body.get('name'))

            # 2. S3 Image Handling
            image_url = None
            if body.get('image'):
                s3_client = boto3.client('s3')
                file_name = f"profile_{active_id}.jpg"
                image_bytes = base64.b64decode(body.get('image'))
                
                s3_client.put_object(
                    Bucket=os.environ['BUCKET_NAME'],
                    Key=file_name,
                    Body=image_bytes,
                    ContentType='image/jpeg'
                )
                region = os.environ.get('AWS_REGION', 'eu-central-1')
                image_url = f"https://{os.environ['BUCKET_NAME']}.s3.{region}.amazonaws.com/{file_name}"

            # 3. Update/Insert into 'item_profiles'
            # We use COALESCE to keep the old value if the new one isn't provided in PUT
            conn.run("""
                INSERT INTO item_profiles (item_id, bio, image_url) 
                VALUES (:id, :bio, :url) 
                ON CONFLICT (item_id) DO UPDATE SET 
                    bio = CASE WHEN :bio IS NOT NULL THEN :bio ELSE item_profiles.bio END,
                    image_url = CASE WHEN :url IS NOT NULL THEN :url ELSE item_profiles.image_url END
            """, id=active_id, bio=body.get('bio'), url=image_url)

            return {'statusCode': 200, 'body': json.dumps({'message': f'Success with {method}'})}

        # --- DELETE ---
        elif method == 'DELETE':
            if not item_id:
                return {'statusCode': 400, 'body': json.dumps({'error': 'ID required'})}
            conn.run("DELETE FROM items WHERE id = :id", id=item_id)
            return {'statusCode': 200, 'body': json.dumps({'message': f'Deleted {item_id}'})}

    except Exception as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
    finally:
        if 'conn' in locals():
            conn.close()