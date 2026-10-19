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
