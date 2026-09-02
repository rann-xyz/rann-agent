"""
Pre-built workflows for common tasks
"""

from typing import Dict, List
from dataclasses import dataclass


@dataclass
class Workflow:
    """Workflow definition"""
    name: str
    description: str
    goal: str
    context: str = ""
    tools: List[str] = None
    estimated_time: str = "2-5 minutes"


class WorkflowLibrary:
    """Library of pre-built workflows"""
    
    WORKFLOWS = {
        "deploy-vercel": Workflow(
            name="deploy-vercel",
            description="Deploy your app to Vercel",
            goal="Deploy the current application to Vercel",
            context="""
            Steps:
            1. Check if vercel CLI is installed
            2. Run vercel build
            3. Run vercel deploy --prod
            4. Show deployment URL
            """,
            tools=["terminal"],
            estimated_time="3-5 minutes"
        ),
        
        "setup-ci": Workflow(
            name="setup-ci",
            description="Set up GitHub Actions CI/CD",
            goal="Create a GitHub Actions workflow for CI/CD",
            context="""
            Create .github/workflows/ci.yml with:
            - Run tests on push
            - Lint code
            - Build project
            - Deploy to production on main branch
            Support for: Python, Node.js, Go based on project
            """,
            tools=["files", "git"],
            estimated_time="2-3 minutes"
        ),
        
        "add-auth": Workflow(
            name="add-auth",
            description="Add JWT authentication",
            goal="Add JWT-based authentication to the API",
            context="""
            Implement:
            - User registration endpoint
            - Login endpoint with JWT token
            - Password hashing (bcrypt)
            - Protected route middleware
            - Token refresh
            """,
            tools=["files", "code_exec"],
            estimated_time="5-10 minutes"
        ),
        
        "generate-crud": Workflow(
            name="generate-crud",
            description="Generate CRUD API endpoints",
            goal="Generate complete CRUD API for a resource",
            context="""
            Generate:
            - Create (POST /)
            - Read all (GET /)
            - Read one (GET /:id)
            - Update (PUT /:id)
            - Delete (DELETE /:id)
            With validation, error handling, and tests
            """,
            tools=["files", "code_exec"],
            estimated_time="4-6 minutes"
        ),
        
        "write-tests": Workflow(
            name="write-tests",
            description="Write tests for untested code",
            goal="Analyze codebase and write tests for untested functions",
            context="""
            1. Find all functions without tests
            2. Generate unit tests
            3. Generate integration tests where needed
            4. Aim for >80% coverage
            5. Run tests to verify they pass
            """,
            tools=["files", "terminal", "code_exec"],
            estimated_time="10-15 minutes"
        ),
        
        "setup-docker": Workflow(
            name="setup-docker",
            description="Create Dockerfile and docker-compose",
            goal="Set up Docker configuration for the project",
            context="""
            Create:
            - Optimized Dockerfile (multi-stage build)
            - docker-compose.yml with services
            - .dockerignore
            - Health checks
            - Environment variable handling
            """,
            tools=["files"],
            estimated_time="3-4 minutes"
        ),
        
        "add-logging": Workflow(
            name="add-logging",
            description="Add structured logging",
            goal="Implement structured logging throughout the application",
            context="""
            Add:
            - Logger configuration
            - Structured log format (JSON)
            - Log levels (debug, info, warn, error)
            - Request logging middleware
            - Error tracking
            """,
            tools=["files", "code_exec"],
            estimated_time="4-5 minutes"
        ),
        
        "setup-db": Workflow(
            name="setup-db",
            description="Set up database with migrations",
            goal="Configure database and migration system",
            context="""
            Set up:
            - Database connection
            - ORM/query builder
            - Migration system
            - Seed data
            - Connection pooling
            Support SQLite, PostgreSQL, MySQL
            """,
            tools=["files", "terminal"],
            estimated_time="5-7 minutes"
        ),
        
        "optimize-performance": Workflow(
            name="optimize-performance",
            description="Analyze and optimize performance",
            goal="Profile application and implement optimizations",
            context="""
            1. Profile the application
            2. Identify bottlenecks
            3. Implement caching
            4. Optimize database queries
            5. Add lazy loading
            6. Minimize bundle size
            """,
            tools=["terminal", "code_exec", "files"],
            estimated_time="10-15 minutes"
        ),
        
        "security-audit": Workflow(
            name="security-audit",
            description="Run security audit and fix issues",
            goal="Audit codebase for security vulnerabilities",
            context="""
            Check for:
            - SQL injection vulnerabilities
            - XSS vulnerabilities
            - Insecure dependencies
            - Exposed secrets
            - Missing input validation
            - CSRF protection
            Auto-fix issues where possible
            """,
            tools=["terminal", "files"],
            estimated_time="5-8 minutes"
        ),
    }
    
    @classmethod
    def get(cls, name: str) -> Workflow:
        """Get workflow by name"""
        return cls.WORKFLOWS.get(name)
    
    @classmethod
    def list_all(cls) -> List[Workflow]:
        """List all workflows"""
        return list(cls.WORKFLOWS.values())
    
    @classmethod
    def search(cls, query: str) -> List[Workflow]:
        """Search workflows by query"""
        query_lower = query.lower()
        return [
            wf for wf in cls.WORKFLOWS.values()
            if query_lower in wf.name.lower() or query_lower in wf.description.lower()
        ]
