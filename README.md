# Mailbox Monitor

An intelligent GitLab issue assignment automation service that monitors email notifications and uses AI to recommend optimal assignees.

## Features

- **Email Monitoring**: Monitors IMAP mailbox for GitLab assignment notifications
- **AI-Powered Assignment**: Uses AI API to predict the best assignee for issues
- **GitLab Integration**: Automatically reassigns issues through GitLab API
- **Containerized Deployment**: Ready for Docker and Docker Compose
- **Configurable Thresholds**: Confidence-based assignment decisions
- **Comprehensive Logging**: Detailed logging for monitoring and debugging
- **Health Checks**: Built-in health monitoring for all services

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Email Server  │    │  Mailbox Monitor │    │   AI API        │
│   (IMAP)        │───►│                  │───►│                 │
└─────────────────┘    │  - Email Parser  │    │ - Assignee      │
                       │  - AI Client     │    │   Prediction    │
                       │  - GitLab Client │    └─────────────────┘
                       └──────────────────┘              │
                                │                        │
                                ▼                        │
                       ┌─────────────────┐               │
                       │  GitLab Server  │◄──────────────┘
                       │  - Issue API    │
                       │  - Assignment   │
                       └─────────────────┘
```

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd mailbox-monitor
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` file with your settings:

```bash
# Email Configuration
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
EMAIL_USERNAME=your-email@example.com
EMAIL_PASSWORD=your-app-specific-password

# AI API Configuration
AI_API_URL=http://ai-api:8000
AI_API_KEY=your-ai-api-key

# GitLab Configuration
GITLAB_URL=https://gitlab.example.com
GITLAB_PRIVATE_TOKEN=your-gitlab-private-token
```

### 3. Run with Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f mailbox-monitor

# Check health
docker-compose exec mailbox-monitor python main.py --health-check
```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `IMAP_SERVER` | IMAP server hostname | - | ✅ |
| `IMAP_PORT` | IMAP server port | 993 | ❌ |
| `EMAIL_USERNAME` | Email username/address | - | ✅ |
| `EMAIL_PASSWORD` | Email password (app-specific for Gmail) | - | ✅ |
| `EMAIL_MAILBOX` | IMAP mailbox to monitor | INBOX | ❌ |
| `AI_API_URL` | AI service base URL | - | ✅ |
| `AI_API_KEY` | AI service API key | - | ❌ |
| `AI_API_TIMEOUT` | AI API request timeout (seconds) | 30 | ❌ |
| `GITLAB_URL` | GitLab instance URL | - | ✅ |
| `GITLAB_PRIVATE_TOKEN` | GitLab private access token | - | ✅ |
| `CHECK_INTERVAL` | Email check interval (seconds) | 60 | ❌ |
| `MIN_CONFIDENCE` | Minimum AI confidence (0.0-1.0) | 0.7 | ❌ |
| `DRY_RUN` | Test mode without actual reassignment | false | ❌ |
| `LOG_LEVEL` | Logging level | INFO | ❌ |

### Email Setup

#### Gmail Configuration

1. Enable 2-factor authentication
2. Generate app-specific password
3. Use app password for `EMAIL_PASSWORD`

#### Other IMAP Providers

- **Outlook**: `outlook.office365.com:993`
- **Yahoo**: `imap.mail.yahoo.com:993`
- **Custom**: Check your provider's IMAP settings

### GitLab Token Setup

1. Go to GitLab → User Settings → Access Tokens
2. Create token with scopes:
   - `api` (full API access)
   - `read_repository` (read repository)
   - `write_repository` (modify issues)

### AI API Requirements

The AI service should provide these endpoints:

#### POST `/predict-assignee`
```json
{
  "issue": {
    "title": "Bug in authentication module",
    "description": "Users cannot login...",
    "labels": ["bug", "authentication"],
    "current_assignee": "john.doe",
    "project": "myorg/myproject"
  }
}
```

Response:
```json
{
  "recommended_assignee": "jane.smith",
  "confidence": 0.85,
  "reasoning": "Based on expertise in authentication modules",
  "alternatives": ["bob.wilson", "alice.cooper"]
}
```

#### GET `/health`
Health check endpoint returning 200 OK.

## Usage

### Command Line Options

```bash
# Run continuous monitoring (default)
python main.py

# Single check cycle
python main.py --check-once

# Health check
python main.py --health-check

# Validate configuration
python main.py --config-check
```

### Docker Commands

```bash
# Build image
docker build -t mailbox-monitor .

# Run container
docker run --env-file .env mailbox-monitor

# Run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/

# Run linting
flake8 *.py

# Run with development settings
LOG_LEVEL=DEBUG DRY_RUN=true python main.py
```

### Testing

```bash
# Test configuration
python main.py --config-check

# Test single cycle
python main.py --check-once

# Test with dry run
DRY_RUN=true python main.py --check-once
```

## Monitoring

### Health Checks

Built-in health checks verify:
- IMAP connection
- AI API availability
- GitLab API connectivity

### Logging

Logs are written to:
- Console (stdout)
- File: `/tmp/mailbox-monitor.log`

Log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`

### Metrics

Monitor these metrics:
- Email processing rate
- AI prediction accuracy
- Assignment success rate
- Service uptime

## Security

### Best Practices

1. **Use app-specific passwords** for email accounts
2. **Limit GitLab token scope** to minimum required
3. **Run as non-root user** in containers
4. **Use environment variables** for secrets
5. **Enable container health checks**
6. **Monitor logs** for suspicious activity

### Network Security

- Services communicate over internal Docker network
- Only necessary ports are exposed
- API keys transmitted over HTTPS

## Troubleshooting

### Common Issues

#### Email Connection Fails
```bash
# Check credentials
python main.py --health-check

# Test IMAP manually
telnet imap.gmail.com 993
```

#### AI API Unreachable
```bash
# Check network connectivity
docker-compose exec mailbox-monitor curl -f http://ai-api:8000/health

# Check logs
docker-compose logs ai-api
```

#### GitLab Permission Denied
```bash
# Verify token permissions
curl -H "PRIVATE-TOKEN: your-token" https://gitlab.example.com/api/v4/user
```

### Debug Mode

```bash
# Enable debug logging
LOG_LEVEL=DEBUG docker-compose up

# Run single cycle with debug
LOG_LEVEL=DEBUG python main.py --check-once
```

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
1. Check troubleshooting section
2. Review logs for error messages
3. Open GitHub issue with details