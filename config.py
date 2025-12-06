# config_improved.py - Enhanced configuration with better validation and error handling
import os
import sys
from pathlib import Path
from typing import List, Optional
from enum import Enum
from pydantic import BaseSettings, Field, validator, root_validator
import logging

class LLMProvider(str, Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"
    GEMINI = "gemini"
    GROK = "grok"

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class Config(BaseSettings):
    """Enhanced configuration with comprehensive validation"""
    
    # LLM Configuration
    LLM_PROVIDER: LLMProvider = LLMProvider.OPENAI
    LLM_MODEL: str = "gpt-4o-mini"
    OPENAI_API_KEY: str = Field("", description="OpenAI API key")
    GEMINI_API_KEY: str = Field("", description="Google Gemini API key")
    XAI_API_KEY: str = Field("", description="xAI API key")
    
    # LLM Parameters
    LLM_TEMPERATURE: float = Field(0.1, ge=0.0, le=2.0)
    LLM_MAX_TOKENS: int = Field(3000, ge=100, le=8000)
    LLM_TIMEOUT: int = Field(60, ge=10, le=300)
    
    # Database Configuration
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string")
    DB_POOL_MIN_SIZE: int = Field(1, ge=1, le=10)
    DB_POOL_MAX_SIZE: int = Field(10, ge=5, le=50)
    DB_TIMEOUT: int = Field(30, ge=5, le=120)
    
    # Google Drive Configuration  
    GOOGLE_CREDENTIALS_FILE: str = Field("credentials.json")
    GOOGLE_DRIVE_FOLDER_ID: str = Field("", description="Google Drive folder ID for monitoring")
    GOOGLE_SCOPES: List[str] = Field(
        default=["https://www.googleapis.com/auth/drive.readonly"],
        description="Google Drive API scopes"
    )
    
    # Processing Configuration
    PROCESSING_ENABLED: bool = Field(True, description="Enable document processing")
    CHUNK_SIZE: int = Field(800, ge=200, le=2000)
    CHUNK_OVERLAP: int = Field(100, ge=50, le=500)
    MAX_RETRIES: int = Field(3, ge=1, le=10)
    RETRY_DELAY: int = Field(30, ge=5, le=300)
    
    # File Processing
    SUPPORTED_FILE_TYPES: List[str] = Field(
        default=[".pdf", ".doc", ".docx"],
        description="Supported file extensions"
    )
    MAX_FILE_SIZE_MB: int = Field(50, ge=1, le=500)
    MAX_PAGES_PER_DOCUMENT: int = Field(200, ge=10, le=1000)
    
    # Email Configuration
    EMAIL_ENABLED: bool = Field(False, description="Enable email notifications")
    EMAIL_SMTP_HOST: Optional[str] = Field(None)
    EMAIL_SMTP_PORT: int = Field(587, ge=25, le=65535)
    EMAIL_USERNAME: Optional[str] = Field(None)
    EMAIL_PASSWORD: Optional[str] = Field(None)
    EMAIL_FROM: str = Field("tenderai@company.com")
    EMAIL_TO: List[str] = Field(default_factory=list)
    EMAIL_USE_TLS: bool = Field(True)
    
    # Security
    SECRET_KEY: str = Field(default_factory=lambda: os.urandom(32).hex())
    ALLOWED_HOSTS: List[str] = Field(default=["localhost", "127.0.0.1"])
    
    # Logging
    LOG_LEVEL: LogLevel = LogLevel.INFO
    LOG_FILE: str = Field("logs/tenderai.log")
    LOG_FORMAT: str = Field("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    LOG_ROTATION_SIZE: str = Field("10MB")
    LOG_BACKUP_COUNT: int = Field(5, ge=1, le=20)
    
    # Performance
    ENABLE_CACHING: bool = Field(True)
    CACHE_TTL_SECONDS: int = Field(3600, ge=60, le=86400)
    CONCURRENT_PROCESSING_LIMIT: int = Field(5, ge=1, le=20)
    
    # Monitoring
    ENABLE_METRICS: bool = Field(False)
    METRICS_PORT: int = Field(8080, ge=1024, le=65535)
    HEALTH_CHECK_ENABLED: bool = Field(True)
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = False
        
    @root_validator
    def validate_configuration(cls, values):
        """Comprehensive configuration validation"""
        errors = []
        
        # Validate LLM configuration
        provider = values.get('LLM_PROVIDER')
        if provider == LLMProvider.OPENAI and not values.get('OPENAI_API_KEY'):
            errors.append("OPENAI_API_KEY is required when using OpenAI provider")
        elif provider == LLMProvider.GEMINI and not values.get('GEMINI_API_KEY'):
            errors.append("GEMINI_API_KEY is required when using Gemini provider")
        elif provider == LLMProvider.GROK and not values.get('XAI_API_KEY'):
            errors.append("XAI_API_KEY is required when using Grok provider")
        
        # Validate database URL format
        db_url = values.get('DATABASE_URL', '')
        if db_url and not db_url.startswith(('postgresql://', 'postgres://')):
            errors.append("DATABASE_URL must be a valid PostgreSQL connection string")
        
        # Validate email configuration if enabled
        if values.get('EMAIL_ENABLED'):
            email_fields = ['EMAIL_SMTP_HOST', 'EMAIL_USERNAME', 'EMAIL_PASSWORD']
            missing_fields = [field for field in email_fields if not values.get(field)]
            if missing_fields:
                errors.append(f"Email enabled but missing required fields: {missing_fields}")
        
        # Validate Google Drive configuration
        if values.get('GOOGLE_DRIVE_FOLDER_ID') and not values.get('GOOGLE_CREDENTIALS_FILE'):
            errors.append("GOOGLE_CREDENTIALS_FILE required when using Google Drive monitoring")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
        
        return values
    
    @validator('CHUNK_OVERLAP')
    def validate_chunk_overlap(cls, v, values):
        """Ensure chunk overlap is smaller than chunk size"""
        chunk_size = values.get('CHUNK_SIZE', 800)
        if v >= chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return v
    
    @validator('DATABASE_URL')
    def validate_database_url(cls, v):
        """Validate database URL format"""
        if v and '://' not in v:
            raise ValueError("DATABASE_URL must include protocol (postgresql://)")
        return v
    
    @validator('GOOGLE_CREDENTIALS_FILE')
    def validate_credentials_file(cls, v):
        """Validate Google credentials file exists if specified"""
        if v and not Path(v).exists():
            # Don't fail validation, just warn
            print(f"Warning: Google credentials file not found: {v}")
        return v
    
    def setup_directories(self):
        """Create necessary directories"""
        directories = [
            Path(self.LOG_FILE).parent,
            Path("downloads"),
            Path("outputs"), 
            Path("templates"),
            Path("cache")
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def setup_logging(self):
        """Configure logging based on settings"""
        logging.basicConfig(
            level=getattr(logging, self.LOG_LEVEL),
            format=self.LOG_FORMAT,
            handlers=[
                logging.FileHandler(self.LOG_FILE),
                logging.StreamHandler(sys.stdout)
            ]
        )
    
    def validate_llm_connection(self) -> bool:
        """Test LLM provider connection"""
        try:
            if self.LLM_PROVIDER == LLMProvider.OPENAI:
                import openai
                client = openai.OpenAI(api_key=self.OPENAI_API_KEY)
                # Simple test call
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Hello"}],
                    max_tokens=5
                )
                return bool(response.choices)
            
            elif self.LLM_PROVIDER == LLMProvider.GEMINI:
                import google.generativeai as genai
                genai.configure(api_key=self.GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content("Hello", 
                    generation_config=genai.types.GenerationConfig(max_output_tokens=5))
                return bool(response.text)
            
            return True
            
        except Exception as e:
            print(f"LLM connection test failed: {e}")
            return False
    
    def get_database_config(self) -> dict:
        """Get database configuration dictionary"""
        return {
            'dsn': self.DATABASE_URL,
            'min_size': self.DB_POOL_MIN_SIZE,
            'max_size': self.DB_POOL_MAX_SIZE,
            'timeout': self.DB_TIMEOUT
        }
    
    @classmethod
    def from_env_file(cls, env_file: str = ".env"):
        """Load configuration from environment file"""
        return cls(_env_file=env_file)

# Global configuration instance
config = None

def get_config() -> Config:
    """Get global configuration instance"""
    global config
    if config is None:
        config = Config()
        config.setup_directories()
        config.setup_logging()
    return config

def validate_environment() -> tuple[bool, List[str]]:
    """Validate entire environment setup"""
    try:
        config = get_config()
        issues = []
        
        # Test LLM connection
        if not config.validate_llm_connection():
            issues.append("LLM provider connection failed")
        
        # Check required files
        if config.GOOGLE_DRIVE_FOLDER_ID:
            if not Path(config.GOOGLE_CREDENTIALS_FILE).exists():
                issues.append(f"Google credentials file missing: {config.GOOGLE_CREDENTIALS_FILE}")
        
        # Check database connection (simplified)
        if not config.DATABASE_URL:
            issues.append("DATABASE_URL not configured")
        
        return len(issues) == 0, issues
        
    except Exception as e:
        return False, [f"Configuration validation failed: {e}"]

if __name__ == "__main__":
    # Test configuration
    print("🔧 Testing TenderAI Configuration")
    print("-" * 40)
    
    try:
        config = get_config()
        print(f"✅ Configuration loaded successfully")
        print(f"   LLM Provider: {config.LLM_PROVIDER}")
        print(f"   Model: {config.LLM_MODEL}")
        print(f"   Database: {'Configured' if config.DATABASE_URL else 'Not configured'}")
        print(f"   Log Level: {config.LOG_LEVEL}")
        
        # Validate environment
        is_valid, issues = validate_environment()
        if is_valid:
            print("✅ Environment validation passed")
        else:
            print("⚠️ Environment issues detected:")
            for issue in issues:
                print(f"   • {issue}")
                
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")