# fib-cache-app

A small Flask API with a Redis cache, built, tested and deployed automatically by a Jenkins pipeline.
This project is the live demo for my course presentation:
**"CI/CD Pipelines and Deployment Automation for Large-Scale Systems: Jenkins"**.

The app is simple on purpose. The goal is to show how Jenkins checks out the code, builds it, tests it and deploys it.

## Table of contents

1. [What the app does](#what-the-app-does)
2. [Project files](#project-files)
3. [Part 1: Run the app from scratch (terminal)](#part-1-run-the-app-from-scratch-terminal)
4. [Part 2: Set up Jenkins from scratch](#part-2-set-up-jenkins-from-scratch)
5. [Part 3: The pipeline](#part-3-the-pipeline)
6. [Demo script: green, then red](#demo-script-green-then-red)
7. [Troubleshooting](#troubleshooting)
8. [Clean up](#clean-up)
9. [Notes and limits](#notes-and-limits)

---

## What the app does

| Endpoint | Description |
|---|---|
| `GET /health` | Returns `{"status": "ok"}` so we know the app is running |
| `GET /compute/<n>` | Returns the n-th Fibonacci number |

`/compute/<n>` waits **5 seconds on purpose**. This stands for a slow database query in a real system.
The result is stored in Redis for **60 seconds** (TTL).

- 1st request: cache miss, about 5 seconds, `"cached": false`
- 2nd request: cache hit, about 0 seconds, `"cached": true`

Example response:

```json
{"cached": false, "duration_seconds": 5, "n": 30, "result": 832040}
```

How it fits together:

```
Browser  ->  Flask API (fib-app)  ->  Redis (fib-redis)

GitHub  ->  Jenkins (Checkout -> Build -> Unit Test -> Deploy)  ->  Docker on the Mac
```

## Project files

| File | Purpose |
|---|---|
| `app.py` | Flask app and Redis cache |
| `test_app.py` | Unit tests (pytest). They use a fake in-memory cache, so no Redis is needed |
| `requirements.txt` | Python libraries (Flask, redis, pytest) with fixed versions |
| `Dockerfile` | Builds the app image (`python:3.12-slim`) |
| `Jenkinsfile` | The pipeline definition (Declarative Pipeline, "Pipeline as Code") |
| `.gitignore` | Keeps `.venv` and cache folders out of Git |

Configuration (environment variables): `REDIS_HOST` (default `localhost`) and `REDIS_PORT` (default `6379`).
The app listens on port `5001`. (Port 5000 is avoided because macOS AirPlay Receiver can use it.)

---

## Part 1: Run the app from scratch (terminal)

### Requirements

- macOS (built and tested on a Mac)
- Docker Desktop, running
- Git
- Python 3 (tested with 3.14; the Docker image uses 3.12)

### 1. Get the code

```bash
git clone https://github.com/utkuares/fib-cache-app.git
cd fib-cache-app
```

### 2. Create a virtual environment and install the libraries

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The `(.venv)` text at the start of the terminal line shows that the environment is active.
Every new terminal tab needs `source .venv/bin/activate` again.

### 3. Run the unit tests

```bash
python -m pytest -v
```

Expected: `5 passed`. The tests use a fake cache, so Redis is not needed yet.

### 4. Start a Redis server in a container

```bash
docker run -d --name redis-dev -p 6379:6379 redis:7-alpine
docker exec redis-dev redis-cli ping
```

Expected: `PONG`.
If the name `redis-dev` already exists, check it with `docker ps -a --filter name=redis-dev`.
If it is running, just use it. If it is stopped, start it with `docker start redis-dev`.

### 5. Start the app

If the Jenkins pipeline already deployed the app, port 5001 is taken by the `fib-app` container. Stop it first:

```bash
docker stop fib-app
```

(Ignore this if you have never run the pipeline. If the container does not exist, Docker prints an error that you can ignore.)

```bash
python app.py
```

Open these addresses in a browser:

- `http://localhost:5001/health` -> `{"status": "ok"}`
- `http://localhost:5001/compute/30` -> about 5 seconds, `cached: false`
- Refresh the same page -> instant, `cached: true`

Stop the app with `Ctrl + C`.

### 6. Look inside Redis (optional)

```bash
docker exec redis-dev redis-cli get fib:30
docker exec redis-dev redis-cli ttl fib:30
```

`get` shows the stored result (`832040`), `ttl` shows the seconds left before Redis deletes it.
After the TTL ends, `get` is empty and `ttl` is `-2`.

### 7. Build and test the Docker image

```bash
docker build -t fib-cache-app:local .
docker run --rm fib-cache-app:local python -m pytest -v
```

Expected: `5 passed`. The tests run inside the image, so no local Python is needed.
This is the same thing the Jenkins pipeline does in its Build and Unit Test stages.

---

## Part 2: Set up Jenkins from scratch

Jenkins runs in a Docker container on the Mac. Two connections matter:

- `jenkins_home` volume: keeps jobs and build history, even if the container is deleted
- `docker.sock`: lets the pipeline send Docker commands to Docker on the Mac

### 1. Build the Jenkins image with the Docker CLI

The official Jenkins image does not include the Docker CLI. The pipeline needs it, so a small custom image called `jenkins-with-docker` is built.
It takes the official `jenkins/jenkins:lts` image and copies only the `docker` command into it from the official `docker:cli` image.
Create a folder `jenkins-docker/` with a file named `Dockerfile`:

```dockerfile
FROM jenkins/jenkins:lts
USER root
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/docker
USER jenkins
```

Then build it:

```bash
docker build -t jenkins-with-docker ./jenkins-docker
docker run --rm --entrypoint docker jenkins-with-docker --version
```

The second command should print `Docker version ...`.

> The image also needs `git`; the official Jenkins image already includes it.
> If you already have a container called `jenkins` (see Clean up), use another name and port, for example `jenkins-test` and `-p 8081:8080`.

### 2. Start the Jenkins container

```bash
docker run -d --name jenkins \
  --user root \
  -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jenkins-with-docker
```

What the options do:

- `--user root`: needed so Jenkins can use the Docker socket on Docker Desktop (without it: `permission denied`)
- `-p 8080:8080`: the Jenkins web page
- `-v jenkins_home:/var/jenkins_home`: the data volume
- `-v /var/run/docker.sock:/var/run/docker.sock`: the Docker connection

Security note: giving Jenkins access to `docker.sock` gives it wide control over Docker.
This is acceptable for a local demo. Real production systems handle it more carefully.

### 3. Check that Jenkins can use Docker

```bash
docker exec jenkins docker ps
docker exec jenkins git --version
```

Both should work. (The Jenkins container has no Python and no `docker compose`. That is why the pipeline runs tests inside the app image and deploys with plain `docker` commands.)

### 4. First setup in the browser

1. Open `http://localhost:8080` (Chrome shows the English interface)
2. Unlock Jenkins with the initial admin password:
   ```bash
   docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
   ```
3. Choose **Install suggested plugins**
4. Create the admin user. Save the username and password in a password manager.
   Jenkins shows "Invalid username or password" for both a wrong name and a wrong password.

### 5. Optional: a small check job

Create a Pipeline job named `docker-check` and paste this script. It proves that Docker works from inside a pipeline:

```groovy
pipeline {
    agent any
    stages {
        stage('Docker Check') {
            steps {
                sh 'docker version'
                sh 'docker ps'
            }
        }
    }
}
```

Run **Build Now**. The Console Output should show a `Server:` section and `Finished: SUCCESS`.

### 6. Create the pipeline job

1. **New Item** -> name: `fib-cache-app-pipeline` -> type: **Pipeline** -> **OK**
2. In the **Pipeline** section:
   - Definition: **Pipeline script from SCM** (not "Pipeline script")
   - SCM: **Git**
   - Repository URL: `https://github.com/utkuares/fib-cache-app.git`
   - Credentials: `- none -` (the repository is public)
   - Branches to build: only `*/main` (remove any `*/master` row with the red X)
   - Script Path: `Jenkinsfile`
   - Leave **Advanced** and **Additional Behaviours** empty
3. **Save**, then **Build Now**
4. Open the build number (`#1`), then **Console Output**. Look for `5 passed` and `Finished: SUCCESS`.

---

## Part 3: The pipeline

The `Jenkinsfile`:

```groovy
pipeline {
    agent any

    environment {
        IMAGE = "fib-cache-app:${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        stage('Build') {
            steps {
                sh 'docker build -t $IMAGE .'
            }
        }
        stage('Unit Test') {
            steps {
                sh 'docker run --rm $IMAGE python -m pytest -v'
            }
        }
        stage('Deploy') {
            steps {
                sh '''
                    docker network create fib-net || true
                    docker rm -f fib-app fib-redis || true
                    docker run -d --name fib-redis --network fib-net redis:7-alpine
                    docker run -d --name fib-app --network fib-net -e REDIS_HOST=fib-redis -p 5001:5001 $IMAGE
                '''
            }
        }
    }
}
```

| Stage | What happens |
|---|---|
| (Declarative: Checkout SCM) | Jenkins adds this stage itself. It fetches the `Jenkinsfile` from GitHub |
| Checkout | Pulls the application code |
| Build | Builds the Docker image `fib-cache-app:<build number>` |
| Unit Test | Runs `pytest` inside that image |
| Deploy | Creates the `fib-net` network and starts `fib-redis` and `fib-app` (port 5001) |

Words used in Jenkins:

- **Job**: the defined work (`fib-cache-app-pipeline`). Visible in Jenkins.
- **Build**: one run of the job (`#1`, `#2`...). Visible in Jenkins.
- **Stage** and **step**: written inside the `Jenkinsfile`. A stage is a phase, a step is one command (`sh '...'`).

If a test fails, the pipeline stops at **Unit Test** and **Deploy does not run**. The last good version keeps running.

Deploy removes the old `fib-app` and `fib-redis` containers on every run (`docker rm -f`) and creates new ones. It does not touch the `jenkins` or `redis-dev` containers.

### Check the deployment

- `http://localhost:5001/health` -> `{"status": "ok"}`
- `http://localhost:5001/compute/35` -> about 5 seconds, `cached: false`; refresh -> instant, `cached: true`

Use a new number each time you test (35, 36, 37...). A result stays in Redis for 60 seconds.

---

## Demo script: green, then red

1. In Jenkins, open `fib-cache-app-pipeline` and click **Build Now**. All stages turn green.
2. Open `http://localhost:5001/compute/40` twice: slow first, instant second.
3. Break a test on purpose (the 10th Fibonacci number is 55, we write 56):
   ```bash
   sed -i '' 's/fibonacci(10) == 55/fibonacci(10) == 56/' test_app.py
   git add test_app.py && git commit -m "Break a test on purpose for the demo" && git push
   ```
4. Click **Build Now** again. The pipeline turns red at **Unit Test**, and **Deploy does not run**.
5. Fix the test and push again:
   ```bash
   sed -i '' 's/fibonacci(10) == 56/fibonacci(10) == 55/' test_app.py
   git add test_app.py && git commit -m "Fix the test" && git push
   ```
6. Click **Build Now**. The pipeline is green again.

Tip: record the demo screen with `Cmd + Shift + 5` as a backup, and turn on Do Not Disturb before the demo.

---

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| `command not found: python` | The virtual environment is not active in this tab. Run `source .venv/bin/activate` |
| Typing a command after `>>>` gives `SyntaxError` | You are inside Python. Type `exit()` and use the normal terminal (`%`) |
| `Address already in use` on port 5001 | An old app is still running. Check with `lsof -i :5001` and stop it with `Ctrl + C` in its window |
| `container name "/redis-dev" is already in use` | It already exists. Use it, or start it with `docker start redis-dev` |
| Both requests are slow (`cached: false`) | The first result is older than 60 seconds, or you used the same number after the TTL ended. Try a new number |
| `permission denied` for Docker in Jenkins | Start the Jenkins container with `--user root` and mount `/var/run/docker.sock` |
| `python3: executable file not found` in Jenkins | Python is not in the Jenkins container. Tests must run inside the app image (as the Jenkinsfile does) |
| `docker compose` not found in Jenkins | Not installed there. The pipeline uses plain `docker` commands instead |
| Build is red at Checkout | Check the repository URL and that the branch is `*/main` |
| Jenkins login fails | Check the saved username and password. The username is the part before the `_` in `/var/jenkins_home/users/` folder names (lowercase) |

---

## Clean up

These commands only remove the containers and network created for this project:

```bash
docker rm -f fib-app fib-redis redis-dev
docker network rm fib-net
```

Do **not** remove the `jenkins` container or the `jenkins_home` volume if you want to keep your Jenkins jobs and build history.

## Notes and limits

- Builds are started manually with **Build Now**. Triggering from GitHub with a webhook needs a public address (a tunnel), so it is left as a future improvement. SCM polling can be added later.
- The Flask built-in server is used for the demo. Production systems use a WSGI server such as Gunicorn.
- Unit tests use a fake cache. A test against a real Redis (integration test) is not included.
- Jenkins runs the build on its own container (no separate agent). Large systems use separate agent machines.
