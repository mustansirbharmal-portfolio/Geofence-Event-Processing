#!/usr/bin/env python3
"""
Deployment script for the Geofence Event Processing System.
Handles environment setup, dependency installation, and service startup.
"""

import os
import sys
import subprocess
import argparse
import json
from pathlib import Path


def run_command(command, check=True, shell=True):
    """Run a command and return the result."""
    print(f"Running: {command}")
    try:
        result = subprocess.run(
            command, 
            shell=shell, 
            check=check, 
            capture_output=True, 
            text=True
        )
        if result.stdout:
            print(result.stdout)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        if check:
            sys.exit(1)
        return e


def check_prerequisites():
    """Check if required tools are installed."""
    print("🔍 Checking prerequisites...")
    
    requirements = {
        'python': 'python --version',
        'pip': 'pip --version',
        'redis': 'redis-cli --version',
    }
    
    missing = []
    for tool, command in requirements.items():
        result = run_command(command, check=False)
        if result.returncode != 0:
            missing.append(tool)
        else:
            print(f"✅ {tool} is available")
    
    if missing:
        print(f"❌ Missing requirements: {', '.join(missing)}")
        print("Please install the missing tools and try again.")
        return False
    
    print("✅ All prerequisites are available")
    return True


def setup_environment():
    """Set up the Python virtual environment."""
    print("🐍 Setting up Python environment...")
    
    # Create virtual environment if it doesn't exist
    if not Path('venv').exists():
        print("Creating virtual environment...")
        run_command(f"{sys.executable} -m venv venv")
    
    # Determine activation script path
    if os.name == 'nt':  # Windows
        activate_script = 'venv\\Scripts\\activate'
        pip_path = 'venv\\Scripts\\pip'
        python_path = 'venv\\Scripts\\python'
    else:  # Unix/Linux/macOS
        activate_script = 'venv/bin/activate'
        pip_path = 'venv/bin/pip'
        python_path = 'venv/bin/python'
    
    print("Installing dependencies...")
    run_command(f"{pip_path} install --upgrade pip")
    run_command(f"{pip_path} install -r requirements.txt")
    
    return python_path


def check_environment_variables():
    """Check if required environment variables are set."""
    print("🔧 Checking environment variables...")
    
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ .env file not found!")
        print("Please create a .env file with your Azure Cosmos DB credentials.")
        print("See README.md for the required format.")
        return False
    
    required_vars = [
        'COSMOS_ENDPOINT',
        'COSMOS_KEY',
        'COSMOS_DATABASE_NAME',
        'COSMOS_CONTAINER_NAME'
    ]
    
    # Read .env file
    env_vars = {}
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value
    
    missing_vars = [var for var in required_vars if var not in env_vars]
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    print("✅ All required environment variables are set")
    return True


def setup_database(python_path):
    """Set up the Django database."""
    print("🗄️ Setting up database...")
    
    print("Running Django migrations...")
    run_command(f"{python_path} manage.py migrate")
    
    print("Creating cache table...")
    run_command(f"{python_path} manage.py createcachetable", check=False)
    
    print("Collecting static files...")
    run_command(f"{python_path} manage.py collectstatic --noinput")


def test_services(python_path):
    """Test that all services are working."""
    print("🧪 Testing services...")
    
    # Test Django
    print("Testing Django configuration...")
    result = run_command(f"{python_path} manage.py check", check=False)
    if result.returncode != 0:
        print("❌ Django configuration has issues")
        return False
    
    # Test Redis connection
    print("Testing Redis connection...")
    result = run_command("redis-cli ping", check=False)
    if result.returncode != 0:
        print("❌ Redis is not running or not accessible")
        print("Please start Redis server: redis-server")
        return False
    
    print("✅ All services are working")
    return True


def start_development_server(python_path):
    """Start the development server."""
    print("🚀 Starting development server...")
    print("Server will be available at: http://localhost:8000")
    print("Dashboard: http://localhost:8000")
    print("API Documentation: See README.md")
    print("Press Ctrl+C to stop the server")
    
    try:
        run_command(f"{python_path} manage.py runserver 0.0.0.0:8000")
    except KeyboardInterrupt:
        print("\n👋 Server stopped")


def start_production_server(python_path):
    """Start the production server with Gunicorn."""
    print("🏭 Starting production server...")
    
    # Install gunicorn if not already installed
    run_command(f"{python_path} -m pip install gunicorn")
    
    print("Server will be available at: http://localhost:8000")
    print("Press Ctrl+C to stop the server")
    
    try:
        run_command(f"gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 120 geofence_event_processing_project.wsgi:application")
    except KeyboardInterrupt:
        print("\n👋 Server stopped")


def docker_deployment():
    """Deploy using Docker."""
    print("🐳 Starting Docker deployment...")
    
    # Check if Docker is available
    result = run_command("docker --version", check=False)
    if result.returncode != 0:
        print("❌ Docker is not installed or not available")
        return False
    
    result = run_command("docker-compose --version", check=False)
    if result.returncode != 0:
        print("❌ Docker Compose is not installed or not available")
        return False
    
    print("Building and starting services...")
    run_command("docker-compose up --build -d")
    
    print("✅ Docker deployment started")
    print("Services:")
    print("  - Web application: http://localhost:8000")
    print("  - Redis: localhost:6379")
    print("\nTo view logs: docker-compose logs -f")
    print("To stop services: docker-compose down")
    
    return True


def run_tests(python_path):
    """Run the test suite."""
    print("🧪 Running test suite...")
    
    # Run Django tests
    print("Running Django tests...")
    result = run_command(f"{python_path} manage.py test", check=False)
    
    if result.returncode == 0:
        print("✅ All tests passed")
    else:
        print("❌ Some tests failed")
        return False
    
    # Run API tests if test_api.py exists
    if Path('test_api.py').exists():
        print("Running API integration tests...")
        print("Note: Make sure the server is running before running API tests")
        result = run_command(f"{python_path} test_api.py", check=False)
        
        if result.returncode == 0:
            print("✅ API tests passed")
        else:
            print("❌ API tests failed")
    
    return True


def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(description='Deploy Geofence Event Processing System')
    parser.add_argument('--mode', choices=['dev', 'prod', 'docker', 'test'], 
                       default='dev', help='Deployment mode')
    parser.add_argument('--skip-checks', action='store_true', 
                       help='Skip prerequisite checks')
    parser.add_argument('--no-setup', action='store_true', 
                       help='Skip environment setup')
    
    args = parser.parse_args()
    
    print("🚀 Geofence Event Processing System Deployment")
    print("=" * 50)
    
    # Change to script directory
    os.chdir(Path(__file__).parent)
    
    if not args.skip_checks:
        if not check_prerequisites():
            return 1
        
        if not check_environment_variables():
            return 1
    
    if args.mode == 'docker':
        return 0 if docker_deployment() else 1
    
    python_path = 'python'
    if not args.no_setup:
        python_path = setup_environment()
        setup_database(python_path)
    
    if not test_services(python_path):
        return 1
    
    if args.mode == 'test':
        return 0 if run_tests(python_path) else 1
    elif args.mode == 'dev':
        start_development_server(python_path)
    elif args.mode == 'prod':
        start_production_server(python_path)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
