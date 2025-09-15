"""
Main application entry point for the mailbox-monitor service.
Orchestrates email monitoring, AI prediction, and GitLab assignment updates.
"""

import os
import sys
import logging
import time
from typing import Dict, Optional
from dotenv import load_dotenv

from email_monitor import EmailMonitor
from ai_client import AIClient
from gitlab_client import GitLabClient


class MailboxMonitor:
    """Main application class for monitoring mailbox and managing GitLab assignments."""
    
    def __init__(self):
        """Initialize the mailbox monitor with configuration from environment."""
        # Load environment variables
        load_dotenv()
        
        # Set up logging
        self._setup_logging()
        
        # Initialize configuration
        self.config = self._load_configuration()
        
        # Initialize clients
        self.email_monitor = None
        self.ai_client = None
        self.gitlab_client = None
        
        self._initialize_clients()
    
    def _setup_logging(self):
        """Set up application logging."""
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        logging.basicConfig(
            level=getattr(logging, log_level),
            format=log_format,
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('/tmp/mailbox-monitor.log')
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Mailbox Monitor starting up...")
    
    def _load_configuration(self) -> Dict:
        """Load configuration from environment variables."""
        config = {}
        
        # Email configuration
        config['email'] = {
            'imap_server': os.getenv('IMAP_SERVER'),
            'imap_port': int(os.getenv('IMAP_PORT', '993')),
            'username': os.getenv('EMAIL_USERNAME'),
            'password': os.getenv('EMAIL_PASSWORD'),
            'mailbox': os.getenv('EMAIL_MAILBOX', 'INBOX')
        }
        
        # AI API configuration
        config['ai'] = {
            'api_url': os.getenv('AI_API_URL'),
            'api_key': os.getenv('AI_API_KEY'),
            'timeout': int(os.getenv('AI_API_TIMEOUT', '30'))
        }
        
        # GitLab configuration
        config['gitlab'] = {
            'url': os.getenv('GITLAB_URL'),
            'private_token': os.getenv('GITLAB_PRIVATE_TOKEN')
        }
        
        # Application configuration
        config['app'] = {
            'check_interval': int(os.getenv('CHECK_INTERVAL', '60')),
            'min_confidence': float(os.getenv('MIN_CONFIDENCE', '0.7')),
            'dry_run': os.getenv('DRY_RUN', 'false').lower() == 'true'
        }
        
        # Validate required configuration
        self._validate_configuration(config)
        
        return config
    
    def _validate_configuration(self, config: Dict):
        """Validate that all required configuration is present."""
        required_fields = [
            ('email', 'imap_server'),
            ('email', 'username'),
            ('email', 'password'),
            ('ai', 'api_url'),
            ('gitlab', 'url'),
            ('gitlab', 'private_token')
        ]
        
        missing_fields = []
        for section, field in required_fields:
            if not config.get(section, {}).get(field):
                missing_fields.append(f"{section}.{field}")
        
        if missing_fields:
            raise ValueError(f"Missing required configuration: {', '.join(missing_fields)}")
    
    def _initialize_clients(self):
        """Initialize email monitor, AI client, and GitLab client."""
        try:
            # Initialize email monitor
            self.email_monitor = EmailMonitor(
                imap_server=self.config['email']['imap_server'],
                imap_port=self.config['email']['imap_port'],
                username=self.config['email']['username'],
                password=self.config['email']['password']
            )
            
            # Initialize AI client
            self.ai_client = AIClient(
                api_url=self.config['ai']['api_url'],
                api_key=self.config['ai']['api_key'],
                timeout=self.config['ai']['timeout']
            )
            
            # Initialize GitLab client
            self.gitlab_client = GitLabClient(
                gitlab_url=self.config['gitlab']['url'],
                private_token=self.config['gitlab']['private_token']
            )
            
            self.logger.info("All clients initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize clients: {e}")
            raise
    
    def health_check(self) -> bool:
        """
        Perform health check on all services.
        
        Returns:
            True if all services are healthy, False otherwise
        """
        self.logger.info("Performing health check...")
        
        checks = []
        
        # Check email connection
        if self.email_monitor.connect():
            self.email_monitor.disconnect()
            checks.append(True)
            self.logger.info("✓ Email connection healthy")
        else:
            checks.append(False)
            self.logger.error("✗ Email connection failed")
        
        # Check AI API
        if self.ai_client.health_check():
            checks.append(True)
            self.logger.info("✓ AI API healthy")
        else:
            checks.append(False)
            self.logger.error("✗ AI API failed")
        
        # Check GitLab API
        if self.gitlab_client.health_check():
            checks.append(True)
            self.logger.info("✓ GitLab API healthy")
        else:
            checks.append(False)
            self.logger.error("✗ GitLab API failed")
        
        all_healthy = all(checks)
        if all_healthy:
            self.logger.info("All services are healthy")
        else:
            self.logger.error("Some services are unhealthy")
        
        return all_healthy
    
    def process_gitlab_notification(self, email_data: Dict) -> bool:
        """
        Process a GitLab assignment notification email.
        
        Args:
            email_data: Parsed email data from EmailMonitor
            
        Returns:
            True if processed successfully, False otherwise
        """
        try:
            self.logger.info(f"Processing GitLab notification for issue: {email_data.get('title', 'Unknown')}")
            
            # Skip if no URL found
            if not email_data.get('url'):
                self.logger.warning("No issue URL found in email, skipping")
                return False
            
            # Get AI prediction for assignee
            ai_prediction = self.ai_client.predict_assignee(email_data)
            if not ai_prediction:
                self.logger.error("Failed to get AI prediction, skipping")
                return False
            
            recommended_assignee = ai_prediction.get('recommended_assignee')
            confidence = ai_prediction.get('confidence', 0)
            reasoning = ai_prediction.get('reasoning', '')
            
            self.logger.info(f"AI recommendation: {recommended_assignee} (confidence: {confidence:.2f})")
            
            # Check confidence threshold
            if confidence < self.config['app']['min_confidence']:
                self.logger.info(f"Confidence {confidence:.2f} below threshold {self.config['app']['min_confidence']}, skipping")
                return False
            
            # Check if assignment change is needed
            current_assignee = email_data.get('current_assignee', '')
            if current_assignee == recommended_assignee:
                self.logger.info(f"Issue already assigned to recommended assignee: {recommended_assignee}")
                return True
            
            # Perform assignment if not in dry run mode
            if self.config['app']['dry_run']:
                self.logger.info(f"DRY RUN: Would reassign issue to {recommended_assignee}")
                return True
            else:
                success = self.gitlab_client.process_reassignment(
                    issue_url=email_data['url'],
                    new_assignee=recommended_assignee,
                    ai_reasoning=reasoning
                )
                
                if success:
                    self.logger.info(f"Successfully reassigned issue to {recommended_assignee}")
                else:
                    self.logger.error(f"Failed to reassign issue to {recommended_assignee}")
                
                return success
                
        except Exception as e:
            self.logger.error(f"Error processing GitLab notification: {e}")
            return False
    
    def run_once(self) -> int:
        """
        Run a single check cycle.
        
        Returns:
            Number of emails processed
        """
        try:
            # Get new emails
            new_emails = self.email_monitor.get_new_gitlab_emails(self.config['email']['mailbox'])
            
            if not new_emails:
                self.logger.debug("No new GitLab emails found")
                return 0
            
            self.logger.info(f"Found {len(new_emails)} new GitLab notification(s)")
            
            # Process each email
            processed_count = 0
            for email_data in new_emails:
                if self.process_gitlab_notification(email_data):
                    processed_count += 1
                
                # Small delay between processing emails
                time.sleep(1)
            
            self.logger.info(f"Successfully processed {processed_count}/{len(new_emails)} emails")
            return processed_count
            
        except Exception as e:
            self.logger.error(f"Error in run cycle: {e}")
            return 0
    
    def run_continuous(self):
        """Run continuous monitoring loop."""
        self.logger.info("Starting continuous monitoring...")
        
        # Perform initial health check
        if not self.health_check():
            self.logger.error("Initial health check failed, exiting")
            sys.exit(1)
        
        try:
            while True:
                self.run_once()
                
                # Wait for next check
                time.sleep(self.config['app']['check_interval'])
                
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
        except Exception as e:
            self.logger.error(f"Unexpected error in continuous monitoring: {e}")
            raise
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources."""
        self.logger.info("Cleaning up...")
        
        if self.email_monitor:
            self.email_monitor.disconnect()
        
        self.logger.info("Cleanup complete")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Mailbox Monitor for GitLab Assignment Automation')
    parser.add_argument('--check-once', action='store_true', help='Run a single check cycle and exit')
    parser.add_argument('--health-check', action='store_true', help='Perform health check and exit')
    parser.add_argument('--config-check', action='store_true', help='Validate configuration and exit')
    
    args = parser.parse_args()
    
    try:
        monitor = MailboxMonitor()
        
        if args.config_check:
            print("✓ Configuration is valid")
            sys.exit(0)
        
        if args.health_check:
            if monitor.health_check():
                print("✓ All services are healthy")
                sys.exit(0)
            else:
                print("✗ Some services are unhealthy")
                sys.exit(1)
        
        if args.check_once:
            count = monitor.run_once()
            print(f"Processed {count} emails")
            sys.exit(0)
        
        # Default: run continuously
        monitor.run_continuous()
        
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()