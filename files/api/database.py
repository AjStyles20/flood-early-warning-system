# database.py

# This file handles everything related to connecting to our database.
# We are using SQLite, which is a simple file-based database. It requires no installation.
# We also use SQLAlchemy, which is an Object-Relational Mapper (ORM).
# An ORM is a tool that allows us to interact with the database using Python objects and code,
# instead of having to write raw SQL queries (like "SELECT * FROM telemetry").
# This makes the code much cleaner and easier to defend.

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 1. Define the Database URL.
# This deliberately names a SQLite *file*, rather than using ``sqlite://``.
# ``sqlite://`` creates a temporary, in-memory database that loses every
# telemetry record when the server stops.  ``sqlite:///flood_data.db`` stores
# the database beside the process working directory, allowing readings to
# remain available after a normal FastAPI restart.
DEFAULT_DATABASE_URL = "sqlite:///flood_data.db"
# Production deployments can switch to MySQL or MariaDB by setting the
# FLOOD_EWS_DATABASE_URL environment variable, e.g.:
# mysql+pymysql://app_user:StrongPassword@localhost:3306/floodwatch
# Automated tests can inject an isolated database before importing this module.
# Normal server use always takes the persistent file-based default above.
SQLALCHEMY_DATABASE_URL = os.getenv("FLOOD_EWS_DATABASE_URL", DEFAULT_DATABASE_URL)

# 2. Create the Database Engine.
engine_kwargs = {"pool_pre_ping": True}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
elif "mysql" in SQLALCHEMY_DATABASE_URL:
    try:
        import pymysql  # noqa: F401 - ensures the MySQL driver is available
    except ImportError as exc:  # pragma: no cover - environment-specific guard
        raise RuntimeError(
            "MySQL support requires the PyMySQL package. Install it with: pip install pymysql"
        ) from exc

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)

# 3. Create a SessionLocal class.
# A "session" is like a temporary workspace or a single conversation with the database.
# Each time someone makes a request to our API, we will create a brand new session, 
# do some work (like reading or saving sensor data), and then close the session.
# 'autocommit=False' means we have to explicitly say "save my changes now" in our code. This prevents accidental saves.
# 'autoflush=False' stops SQLAlchemy from automatically trying to push changes to the database before we are fully ready.
# 'bind=engine' connects this session factory to the engine we created above.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Create a Base class.
# We will use this 'Base' class later in our 'models.py' file.
# Think of it as a master blueprint. When we define what a "Sensor Reading" looks like in Python,
# we will inherit from this 'Base' class. SQLAlchemy will then automatically know to turn that Python class
# into a real table inside our SQLite database.
Base = declarative_base()

# 5. Define a database connection Dependency (Helper Function).
# We will use this function in our main API file ('main.py').
# Whenever a web request comes in and needs to talk to the database, it will call this function.
# The "yield" keyword is important here. It means: "Pause here, give the database session to the web request, 
# and wait until the web request is completely finished."
# Once the web request finishes (or if it crashes), the code resumes at the "finally" block.
def get_db():
    db = SessionLocal() # Open a new temporary workspace/connection to the database
    try:
        yield db        # Hand it over to the FastAPI endpoint that needs it
    finally:
        db.close()      # GUARANTEE that we close the connection when done, to prevent the database from locking up!
