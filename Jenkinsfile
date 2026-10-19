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
    }
}
