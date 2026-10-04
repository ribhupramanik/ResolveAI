import os

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

load_dotenv()


database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise RuntimeError("DATABASE_URL is not configured.")


test_database_url = make_url(database_url).set(database="resolveai_test")


os.environ["DATABASE_URL"] = test_database_url.render_as_string(hide_password=False)
