# newpage


## Setup Instructions

1. Clone the repository to your local machine using the following command:
   ```
   git clone <repository-url>
   ```
   
### Backend (job-service)

The backend can be ran locally via poetry or via docker containers. It is recommended to attempt running locally as the docker image may take a while to build.

#### Local Deployment

2. Create a virtual environment within the job-service directory and activate:
   ```
   cd job-service
   
   python -m venv venv
   
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```
3. Install poetry within the virtual environment:
   ```
   pip install poetry
   ```
4. Install the project dependencies using poetry:
   ```
   poetry lock
   poetry install  # It may take a while to install torch
   ```
5. Start the backend service:
   ```
    poetry run uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000 --app-dir src
   ```
   
#### Docker Deployment

### Front end
