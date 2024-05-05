import os


def get_secret(secret_name: str) -> str | None:
    lowercase_secret_name = secret_name.lower()
    uppercase_secret_name = secret_name.upper()

    secrets_path = f"/run/secrets/{lowercase_secret_name}"
    if os.path.exists(secrets_path):
        with open(secrets_path) as f:
            return f.read()
    else:
        return os.environ.get(uppercase_secret_name)
