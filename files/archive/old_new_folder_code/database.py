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
from sqlalchemy.pool import StaticPool

# 1. Define the Database URL.
# We are using a purely in-memory database ("sqlite://") for this virtual test.
# This avoids any strict Windows file permission errors and runs lightning fast.
SQLALCHEMY_DATABASE_URL = "sqlite://"

# 2. Create the Database Engine.
# We add StaticPool so that different threads can share this same in-memory database.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

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
