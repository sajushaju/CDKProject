
import json
import os
import boto3
import pg8000.native

def get_secrets():
    try:
        secret_name = os.environ['DB_SECRET_ARN']
        region_name = os.environ.get('AWS_REGION', 'eu-central-1')
        client = boto3.client('secretsmanager', region_name=region_name)
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        raise Exception(f"Failed to retrieve secrets: {str(e)}")

def main(event, context):
    conn = None
    try:
        # 1. Database Connection with Error Handling
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
        except Exception as e:
            return {'statusCode': 500, 'body': json.dumps({'error': f"Database connection failed: {str(e)}"})}

        # 2. Table Setup (Internal logic error handling)
        try:
            conn.run("CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, name TEXT);")
            conn.run("""
                CREATE TABLE IF NOT EXISTS item_profiles (
                    item_id TEXT PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
                    bio TEXT,
                    image_url TEXT
                );
            """)
        except Exception as e:
            return {'statusCode': 500, 'body': json.dumps({'error': f"Table initialization failed: {str(e)}"})}

        method = event.get('httpMethod')
        
        # This captures the ID from the URL (e.g., /items/1)
        path_params = event.get('pathParameters') or {}
        item_id = path_params.get('proxy')

        # --- GET LOGIC ---
        if method == 'GET':
            try:
                if item_id:
                    query = """
                        SELECT i.id, i.name, p.bio, p.image_url 
                        FROM items i 
                        LEFT JOIN item_profiles p ON i.id = p.item_id 
                        WHERE i.id = :id
                    """
                    rows = conn.run(query, id=item_id)
                    if not rows:
                        return {'statusCode': 404, 'body': json.dumps({'error': f'Item {item_id} not found'})}
                    r = rows[0]
                    return {'statusCode': 200, 'body': json.dumps({'id': r[0], 'name': r[1], 'bio': r[2], 'image_url': r[3]})}
                
                rows = conn.run("SELECT id, name FROM items")
                return {'statusCode': 200, 'body': json.dumps([{'id': r[0], 'name': r[1]} for r in rows])}
            except Exception as e:
                return {'statusCode': 500, 'body': json.dumps({'error': f"Read operation failed: {str(e)}"})}

        # --- POST & PUT LOGIC ---
        elif method in ['POST', 'PUT']:
            try:
                body = json.loads(event.get('body', '{}'))
            except json.JSONDecodeError:
                return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid JSON body'})}

            active_id = item_id if method == 'PUT' else body.get('id')
            if not active_id:
                return {'statusCode': 400, 'body': json.dumps({'error': 'ID is required'})}

            # 1. Update/Insert into 'items'
            if body.get('name'):
                conn.run("INSERT INTO items (id, name) VALUES (:id, :name) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name", 
                         id=active_id, name=body.get('name'))

            # 2. S3 Image Handling with Type Validation
            image_url = None
            raw_image_data = body.get('image')
            
            if raw_image_data:
                # Handle Data URI prefix if present (e.g., data:image/png;base64,...)
                ext = "jpg" # Default
                if "," in raw_image_data:
                    header, raw_image_data = raw_image_data.split(",")
                    if 'png' in header: ext = "png"
                    elif 'jpeg' in header or 'jpg' in header: ext = "jpg"
                    else:
                        return {'statusCode': 400, 'body': json.dumps({'error': 'Unsupported image type. Only JPG and PNG are allowed.'})}

                try:
                    image_bytes = base64.b64decode(raw_image_data)
                    
                    # Manual Magic Byte Check (Optional but very professional)
                    # PNG starts with \x89PNG, JPG starts with \xff\xd8
                    if image_bytes.startswith(b'\x89PNG'):
                        ext = "png"
                        content_type = 'image/png'
                    elif image_bytes.startswith(b'\xff\xd8'):
                        ext = "jpg"
                        content_type = 'image/jpeg'
                    else:
                        return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid image format. Must be PNG or JPG.'})}

                    s3_client = boto3.client('s3')
                    file_name = f"profile_{active_id}.{ext}"
                    
                    s3_client.put_object(
                        Bucket=os.environ['BUCKET_NAME'],
                        Key=file_name,
                        Body=image_bytes,
                        ContentType=content_type
                    )
                    region = os.environ.get('AWS_REGION', 'eu-central-1')
                    image_url = f"https://{os.environ['BUCKET_NAME']}.s3.{region}.amazonaws.com/{file_name}"
                except Exception as e:
                    return {'statusCode': 500, 'body': json.dumps({'error': f"Image upload failed: {str(e)}"})}

            # 3. Update/Insert into 'item_profiles'
            try:
                conn.run("""
                    INSERT INTO item_profiles (item_id, bio, image_url) 
                    VALUES (:id, :bio, :url) 
                    ON CONFLICT (item_id) DO UPDATE SET 
                        bio = CASE WHEN :bio IS NOT NULL THEN :bio ELSE item_profiles.bio END,
                        image_url = CASE WHEN :url IS NOT NULL THEN :url ELSE item_profiles.image_url END
                """, id=active_id, bio=body.get('bio'), url=image_url)
            except Exception as e:
                return {'statusCode': 500, 'body': json.dumps({'error': f"Database profile update failed: {str(e)}"})}

            return {'statusCode': 200, 'body': json.dumps({'message': f'Successfully processed {method}', 'id': active_id})}

        # --- DELETE LOGIC ---
        elif method == 'DELETE':
            try:
                if not item_id:
                    return {'statusCode': 400, 'body': json.dumps({'error': 'ID required for deletion'})}
                conn.run("DELETE FROM items WHERE id = :id", id=item_id)
                return {'statusCode': 200, 'body': json.dumps({'message': f'Deleted {item_id}'})}
            except Exception as e:
                return {'statusCode': 500, 'body': json.dumps({'error': f"Delete operation failed: {str(e)}"})}

    except Exception as e:
        return {'statusCode': 500, 'body': json.dumps({'error': f"Unexpected Server Error: {str(e)}"})}
    finally:
        if conn:
            conn.close()
