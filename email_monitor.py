"""
Email monitoring module for GitLab assignment notifications.
Monitors IMAP mailbox and extracts issue information from emails.
"""

import imaplib
import email
import logging
import re
import time
from typing import Dict, List, Optional, Tuple
from email.mime.text import MIMEText
from bs4 import BeautifulSoup


class EmailMonitor:
    """Monitors email for GitLab assignment notifications."""
    
    def __init__(self, imap_server: str, imap_port: int, username: str, password: str):
        """Initialize email monitor with IMAP credentials."""
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.username = username
        self.password = password
        self.connection = None
        self.logger = logging.getLogger(__name__)
        
    def connect(self) -> bool:
        """Connect to IMAP server."""
        try:
            self.connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.connection.login(self.username, self.password)
            self.logger.info(f"Connected to IMAP server {self.imap_server}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to IMAP server: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from IMAP server."""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
                self.logger.info("Disconnected from IMAP server")
            except Exception as e:
                self.logger.error(f"Error disconnecting from IMAP server: {e}")
    
    def get_new_gitlab_emails(self, mailbox: str = "INBOX") -> List[Dict]:
        """
        Fetch new GitLab assignment emails from the specified mailbox.
        
        Args:
            mailbox: IMAP mailbox to monitor (default: INBOX)
            
        Returns:
            List of dictionaries containing parsed email data
        """
        if not self.connection:
            if not self.connect():
                return []
        
        try:
            self.connection.select(mailbox)
            
            # Search for unread GitLab emails
            search_criteria = '(UNSEEN FROM "gitlab")'
            _, message_numbers = self.connection.search(None, search_criteria)
            
            emails = []
            for num in message_numbers[0].split():
                try:
                    _, msg_data = self.connection.fetch(num, '(RFC822)')
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    parsed_email = self._parse_gitlab_email(email_message)
                    if parsed_email:
                        emails.append(parsed_email)
                        # Mark as read
                        self.connection.store(num, '+FLAGS', '\\Seen')
                        
                except Exception as e:
                    self.logger.error(f"Error processing email {num}: {e}")
                    
            return emails
            
        except Exception as e:
            self.logger.error(f"Error fetching emails: {e}")
            return []
    
    def _parse_gitlab_email(self, email_message) -> Optional[Dict]:
        """
        Parse GitLab assignment notification email.
        
        Args:
            email_message: Email message object
            
        Returns:
            Dictionary with extracted issue information or None
        """
        try:
            subject = email_message.get('Subject', '')
            sender = email_message.get('From', '')
            
            # Check if this is a GitLab assignment notification
            if not self._is_gitlab_assignment_email(subject, sender):
                return None
            
            # Extract email body
            body = self._extract_email_body(email_message)
            if not body:
                return None
            
            # Parse issue information from email
            issue_info = self._extract_issue_info(subject, body)
            
            if issue_info:
                self.logger.info(f"Parsed GitLab assignment email for issue: {issue_info.get('title', 'Unknown')}")
                return issue_info
                
        except Exception as e:
            self.logger.error(f"Error parsing GitLab email: {e}")
            
        return None
    
    def _is_gitlab_assignment_email(self, subject: str, sender: str) -> bool:
        """Check if email is a GitLab assignment notification."""
        gitlab_indicators = [
            'gitlab' in sender.lower(),
            'assigned you' in subject.lower(),
            'assignee changed' in subject.lower(),
            'was assigned to you' in subject.lower()
        ]
        return any(gitlab_indicators)
    
    def _extract_email_body(self, email_message) -> str:
        """Extract text body from email message."""
        body = ""
        
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
                elif content_type == "text/html" and not body:
                    html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    # Convert HTML to text
                    soup = BeautifulSoup(html_body, 'html.parser')
                    body = soup.get_text()
        else:
            body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            
        return body
    
    def _extract_issue_info(self, subject: str, body: str) -> Optional[Dict]:
        """
        Extract issue information from email subject and body.
        
        Args:
            subject: Email subject line
            body: Email body text
            
        Returns:
            Dictionary with issue information
        """
        try:
            issue_info = {}
            
            # Extract issue URL
            url_pattern = r'https?://[^\s]+/(?:issues|merge_requests)/\d+'
            url_match = re.search(url_pattern, body)
            if url_match:
                issue_info['url'] = url_match.group()
            
            # Extract issue title from subject
            # Common GitLab subject formats:
            # "Issue #123: Title | Project"
            # "Title (#123) | Project"
            title_patterns = [
                r'Issue #\d+:\s*(.+?)\s*\|',
                r'(.+?)\s*\(#\d+\)\s*\|',
                r'(.+?)\s*-\s*Issue #\d+',
                r'(.+?)\s*\|\s*'
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, subject)
                if match:
                    issue_info['title'] = match.group(1).strip()
                    break
            
            # Extract issue number
            issue_num_match = re.search(r'#(\d+)', subject)
            if issue_num_match:
                issue_info['issue_number'] = issue_num_match.group(1)
            
            # Extract current assignee
            assignee_patterns = [
                r'assigned to\s+@?([^\s\n]+)',
                r'assignee:\s*@?([^\s\n]+)',
                r'Assignee:\s*@?([^\s\n]+)'
            ]
            
            for pattern in assignee_patterns:
                match = re.search(pattern, body, re.IGNORECASE)
                if match:
                    issue_info['current_assignee'] = match.group(1).strip()
                    break
            
            # Extract description (first few lines after issue details)
            description_match = re.search(r'(?:Description|Summary):\s*\n(.*?)(?:\n\n|\n---|\nAssignee)', body, re.DOTALL | re.IGNORECASE)
            if description_match:
                issue_info['description'] = description_match.group(1).strip()[:500]  # Limit description length
            
            # Extract labels
            labels_match = re.search(r'Labels?:\s*([^\n]+)', body, re.IGNORECASE)
            if labels_match:
                labels_text = labels_match.group(1).strip()
                issue_info['labels'] = [label.strip() for label in labels_text.split(',') if label.strip()]
            
            # Extract project information
            project_match = re.search(r'(?:Project|Repository):\s*([^\n]+)', body, re.IGNORECASE)
            if project_match:
                issue_info['project'] = project_match.group(1).strip()
            
            return issue_info if issue_info else None
            
        except Exception as e:
            self.logger.error(f"Error extracting issue info: {e}")
            return None
    
    def monitor_continuously(self, callback_func, interval: int = 60, mailbox: str = "INBOX"):
        """
        Continuously monitor mailbox for new GitLab emails.
        
        Args:
            callback_func: Function to call with new emails
            interval: Check interval in seconds
            mailbox: IMAP mailbox to monitor
        """
        self.logger.info(f"Starting continuous monitoring (interval: {interval}s)")
        
        while True:
            try:
                new_emails = self.get_new_gitlab_emails(mailbox)
                if new_emails:
                    self.logger.info(f"Found {len(new_emails)} new GitLab emails")
                    for email_data in new_emails:
                        callback_func(email_data)
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                self.logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in continuous monitoring: {e}")
                time.sleep(interval)
        
        self.disconnect()