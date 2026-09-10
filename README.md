# newpage

_This file is entirely human-generated_

This is the full README containing set up instructions and design.

Please see [plan.md](./plan.md) for my thought process during development.

## Setup Instructions

1. Clone the repository to your local machine using the following command:
   ```
   git clone <repository-url>
   ```
   
### Backend (job-service)

The backend uses poetry as a package manager and can be ran locally via poetry or via docker containers. It is recommended to attempt running locally as the docker image may take a while to build.

2. Create a .env file in the job-service directory with the following content:
   ```
   BEDROCK_API_KEY="<your_bedrock_api_key>"  # A real AWS Bedrock API Key
   SERVICE_KEY="admin"                       # A key to authenticate model switching
   ```
   

#### Local Deployment

3. Create a virtual environment within the job-service directory and activate:
   ```
   cd job-service
   
   python -m venv venv
   
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```
   
4. Install poetry within the virtual environment:
   ```
   pip install poetry
   ```
   
5. Install the project dependencies using poetry:
   ```
   poetry lock
   poetry install  # It may take a while to install torch
   ```

6. (optional) run the backend tests:
   ```
   poetry run pytest
   ```
   
   Expected result: `143 passed, 4 warnings in 6.08`

7. Start the backend service:
   ```
    poetry run uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000 --app-dir src
   ```
   
#### Docker Deployment

8. From the root of the repository, build the Docker image:
   ```
    docker compose build --no-cache job-service
    ```
   
9. Run the Docker container:
   ```
    docker compose up --force-recreate job-service
   ```
   
### Front end

The front end is built with React and vite and must be ran locally as a container has not been created for it.

10. Navigate to the front-end directory and install dependencies:
   ```
   cd webapp
   
   npm install
   ```

11. (optional) Run the front end tests:
   ```
   npm run test
   ```

   Expected result: ` Test Files  7 passed (7) Tests  38 passed (38)`
   
12. Build and run the front end:
   ```
   npm run build
   npm run dev
   ```

### Load the Bedrock Model

13. Assignment of the bedrock model is admin protected. By default, the only allowed model is `openai.gpt-oss-120b-1:0`, this can be changed by setting
    ```
    ALLOWED_MODELS="openai.gpt-oss-120b-1:0,<other_model_name>"
    ```
    in the .env file. To load a model from the approved list, send a POST request to the `/ai/load_model` endpoint using the admin key set in step 2:

   ```
   curl -X POST "http://localhost:8000/ai/load_model" \
      -H "X-API-Key: admin" \
      -H "Content-Type: application/json" \
      -d '{"model":"openai.gpt-oss-120b-1:0"}'

   ```

## System Design

![System Design Diagram](Images\newpage.png "System Design")


The system is kept as simple as possible with a front end (webapp), a backend (job-service) and a vector database (qdrant). All LLM usage is handled by AWS Bedrock.

### Front end

The front end is built using React and runs locally with vite. It consists of three main pages: Job Board, Job Details and Chat.

#### Job Board

[Code](./webapp/src/pages/JobsPage.jsx)

The job board is the main page of the application that displays all the available jobs. Users can then inspect individual jobs that interest them.

At the top of the page is an option to generate a summary of the job board. Users are unable to choose the prompt for this generation. This prompt utilises RAG to obtain relevant information

#### Job Details

[Code](./webapp/src/pages/JobDetailPage.jsx)

This page provides the entire job posting as well as the option to apply for that job.
At this stage, this button is not configured to have any action due to the jobs being fake.

At the top of the page is an option to generate a summary of the job. Users are unable to choose the prompt for this generation.

#### Chat

[Code](./webapp/src/pages/ChatPage.jsx)

This page is the primary function of the application that allows the user to find jobs tailored to their CV. It can be accessed from either the job board or the job details page via a button in the top right. 

Users are required to upload their CV as a PDF before they are able to converse with the AI assistant. Once their CV has been uploaded, then the chat window is enabled and they can ask questions relating to roles and get help with applications such as tailored CV suggestions and interview preparation.

#### Additional Pages

[Health Status](./webapp/src/pages/HealthStatusPage.jsx)
Displays whether the model has been loaded correctly.

[Not Found](./webapp/src/pages/NotFoundPage.jsx)
Displays a 404 page when the user navigates to a non-existent route.

### Backend

The backend is a python application built with FastAPI. It is responsible for handling all requests from the front end, managing the vector database, and interacting with the LLM via AWS Bedrock. 

The [jobs module](./job-service/src/app/api/jobs.py) handles all job-related requests, such as returning all available jobs and details about a specific job.

The [AI module](./job-service/src/app/api/ai.py) is the orchestrator for all LLM requests. It handles loading the model, generating responses, and managing the RAG system. All prompts used are stored here to avoid the user sending custom prompts that are not well defined and may break expected use. 

#### Qdrant Vector Database

This service uses an in-memory vector database (Qdrant) for convenience as opposed to instantiating a standalone service. This was a decision made for convenience in this task, however would be an unacceptable solution if productionising the system. I chose Qdrant because it provided a fast and simple solution that additionally allows custom embeddings.

Embeddings are created at runtime using sentence transformers. By default the `sentence-transformers/all-MiniLM-L6-v2` model is used as it is small and still useful enough to demonstrate my understanding of this task. It would be expected to use a more powerful embedding model in production such as `Voyage` or `Qwen3 Embedding` in production.


#### AWS Bedrock

AWS Bedrock is a managed service for hosting LLMS. This means that I do not have to run any models myself and I had some free credits left over from previous work. 


## Development Decisions

### RAG/LLM approach & technical decisions

Previous work at IOPP has showed me that cosine similarity is a simple but powerful method for finding related content. As a result, the RAG system relies entirely on cosine similarity to find relevant content based on the supplied information. I limited results to the top 3 as I only had 8 mock jobs. Production systems would increase this value considerably. However, the true value would require experimentation to avoid overloading the context window.

I chose to append the rag context to the user query because I have found that marginally more performant in previous practice, however this is based on personal feel and once the context gets too long it likely makes more sense to include it as a context correctly.

During development, I initially used `Tiny Llama 1.1B` as it was small enough to run on my GPU and allowed me to validate the system without having to use the limited credits I had. This was enough for the summary generation (even if the end of the query became messy), however, it only produced gibberish when I attempted to use it for the chat functionality. This meant that I was unable to evaluate any prompt injection defenses or evaluate different prompts.

I opted for `openai.gpt-oss-120b-1` a very large, but cheap model on Bedrock. I was unable to use anthropic models due to using my personal AWS account. I generally consider Claude models to be superior in natural language.

The stack uses React and FastAPI purely due to convenience. I figured that familiarity would enable faster development for an interview assignment as opposed to using a more robust stack such as FastAPI. Although I have familiarity with Angular, I have found that it introduces too many breaking changes during major version upgrades (I have done too many of these on legacy projects for my liking) and so React makes sense if I planned to maintain this application.

The prompts I used for each of the AI-powered systems can be found in [prompts.json](./job-service/src/app/resources/prompts.json)


### Engineering Standards

Overall I have attempted to follow OOP and REST principles as well as siloing my api into sensible modules. For example, I have re-used the summary generation component across both the job board and job details pages. 

My preference in development is to use BDD. Define behaviours, write code to meet those behaviours and create tests as I develop. This ensures that I am constantly thinking of functionality as a whole and reducing bugs that I introduce into systems. I did not follow this practice when developing this assignment because, while it results in more robust code, it takes longer to develop and I will not be productionising this code.

### How I used AI tools in my development process

I use github copilot to aid my development. I primarily used GPT5.3-Codex for code generation and Claude Sonnet 5 for prompt generation. 

The prompts I used have been included in the [prompts folder](./prompts).

The [Review](./prompts/review.md) and [Test](./prompts/test.md) prompts are prompts I obtained online to help review and write tests as I developed.

The [Meta](./prompts/meta.md) prompt is one I received from a coworker which I have used for years as a method for developing well-designed prompts. It allows you to start with a simple sentence or two and iteratively create a strong prompt that is robust to prompt injection via responding to questions.

The [System Prompt Creator](./prompts/system-prompt-creator.md) prompt I created using the meta prompt to help me craft the prompts for this task. The outputs of my conversations with this prompt can be found in [prompts.json](./job-service/src/app/resources/prompts.json)

The [Job Description](./prompts/job-description.md) prompt is the prompt used for generating the fake job listings created using the meta prompt.

### What I would do differently with more time

- Use Jira combined with BDD to coherently create well-defined code in small increments
- Create a standalone database for jobs
- Enable different logins (user/recruiter/admin) to allow posting of new jobs
- Use terraform to deploy the system to AWS (including containerising the front end)
- Use this opportunity to upskill by learning a new skill such as an alternate front end framework or elasticache
- Ensure WCAG AAA web standards are met
- Enable conditional loading of components (such as the generate summary) 


