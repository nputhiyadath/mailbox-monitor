"""
GitLab client module for managing issue assignments.
Uses GitLab API to reassign issues based on AI recommendations.
"""

import gitlab
import logging
import re
from typing import Dict, Optional, List, Tuple
from urllib.parse import urlparse


class GitLabClient:
    """Client for GitLab API operations."""
    
    def __init__(self, gitlab_url: str, private_token: str):
        """
        Initialize GitLab client.
        
        Args:
            gitlab_url: GitLab instance URL
            private_token: GitLab private access token
        """
        self.gitlab_url = gitlab_url.rstrip('/')
        self.private_token = private_token
        self.logger = logging.getLogger(__name__)
        
        try:
            self.gl = gitlab.Gitlab(self.gitlab_url, private_token=self.private_token)
            self.gl.auth()
            self.logger.info(f"Connected to GitLab at {self.gitlab_url}")
        except Exception as e:
            self.logger.error(f"Failed to connect to GitLab: {e}")
            raise
    
    def parse_issue_url(self, issue_url: str) -> Optional[Tuple[str, int]]:
        """
        Parse GitLab issue URL to extract project path and issue IID.
        
        Args:
            issue_url: Full GitLab issue URL
            
        Returns:
            Tuple of (project_path, issue_iid) or None if parsing fails
        """
        try:
            # Parse URL
            parsed = urlparse(issue_url)
            path = parsed.path
            
            # Extract project path and issue IID
            # Expected format: /group/project/-/issues/123 or /group/project/issues/123
            patterns = [
                r'^/([^/]+/[^/]+)/-/issues/(\d+)',
                r'^/([^/]+/[^/]+)/issues/(\d+)',
                r'^/([^/]+/[^/]+)/-/merge_requests/(\d+)',
                r'^/([^/]+/[^/]+)/merge_requests/(\d+)'
            ]
            
            for pattern in patterns:
                match = re.match(pattern, path)
                if match:
                    project_path = match.group(1)
                    issue_iid = int(match.group(2))
                    return project_path, issue_iid
            
            self.logger.error(f"Could not parse GitLab URL: {issue_url}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error parsing GitLab URL {issue_url}: {e}")
            return None
    
    def get_issue(self, project_path: str, issue_iid: int) -> Optional[Dict]:
        """
        Get issue details from GitLab.
        
        Args:
            project_path: GitLab project path (e.g., 'group/project')
            issue_iid: Issue internal ID
            
        Returns:
            Dictionary with issue details or None if failed
        """
        try:
            project = self.gl.projects.get(project_path)
            issue = project.issues.get(issue_iid)
            
            # Extract relevant issue information
            issue_data = {
                'id': issue.id,
                'iid': issue.iid,
                'title': issue.title,
                'description': issue.description,
                'state': issue.state,
                'assignee': None,
                'assignees': [],
                'labels': issue.labels,
                'milestone': None,
                'author': issue.author.get('username') if issue.author else None,
                'created_at': issue.created_at,
                'updated_at': issue.updated_at,
                'web_url': issue.web_url,
                'project_id': issue.project_id
            }
            
            # Handle assignee(s)
            if hasattr(issue, 'assignee') and issue.assignee:
                issue_data['assignee'] = issue.assignee.get('username')
            
            if hasattr(issue, 'assignees') and issue.assignees:
                issue_data['assignees'] = [assignee.get('username') for assignee in issue.assignees]
            
            # Handle milestone
            if hasattr(issue, 'milestone') and issue.milestone:
                issue_data['milestone'] = issue.milestone.get('title')
            
            self.logger.info(f"Retrieved issue {issue_iid} from project {project_path}")
            return issue_data
            
        except gitlab.exceptions.GitlabGetError as e:
            self.logger.error(f"GitLab API error getting issue {issue_iid} from {project_path}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting issue {issue_iid} from {project_path}: {e}")
            return None
    
    def reassign_issue(self, project_path: str, issue_iid: int, new_assignee: str) -> bool:
        """
        Reassign GitLab issue to a new assignee.
        
        Args:
            project_path: GitLab project path
            issue_iid: Issue internal ID
            new_assignee: Username of new assignee
            
        Returns:
            True if successful, False otherwise
        """
        try:
            project = self.gl.projects.get(project_path)
            issue = project.issues.get(issue_iid)
            
            # Get user ID for the new assignee
            assignee_id = self._get_user_id(new_assignee)
            if assignee_id is None:
                self.logger.error(f"Could not find user ID for assignee: {new_assignee}")
                return False
            
            # Update issue assignee
            issue.assignee_id = assignee_id
            issue.save()
            
            self.logger.info(f"Successfully reassigned issue {issue_iid} to {new_assignee}")
            return True
            
        except gitlab.exceptions.GitlabAuthenticationError as e:
            self.logger.error(f"Authentication error reassigning issue: {e}")
            return False
        except gitlab.exceptions.GitlabGetError as e:
            self.logger.error(f"GitLab API error reassigning issue: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error reassigning issue {issue_iid} to {new_assignee}: {e}")
            return False
    
    def add_issue_comment(self, project_path: str, issue_iid: int, comment: str) -> bool:
        """
        Add a comment to a GitLab issue.
        
        Args:
            project_path: GitLab project path
            issue_iid: Issue internal ID
            comment: Comment text
            
        Returns:
            True if successful, False otherwise
        """
        try:
            project = self.gl.projects.get(project_path)
            issue = project.issues.get(issue_iid)
            
            # Create note (comment)
            issue.notes.create({'body': comment})
            
            self.logger.info(f"Added comment to issue {issue_iid}")
            return True
            
        except gitlab.exceptions.GitlabCreateError as e:
            self.logger.error(f"GitLab API error adding comment: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error adding comment to issue {issue_iid}: {e}")
            return False
    
    def get_project_members(self, project_path: str) -> Optional[List[Dict]]:
        """
        Get list of project members who can be assigned to issues.
        
        Args:
            project_path: GitLab project path
            
        Returns:
            List of member dictionaries or None if failed
        """
        try:
            project = self.gl.projects.get(project_path)
            members = project.members.list(all=True)
            
            member_list = []
            for member in members:
                member_info = {
                    'id': member.id,
                    'username': member.username,
                    'name': member.name,
                    'access_level': member.access_level,
                    'state': member.state
                }
                member_list.append(member_info)
            
            self.logger.info(f"Retrieved {len(member_list)} members from project {project_path}")
            return member_list
            
        except gitlab.exceptions.GitlabGetError as e:
            self.logger.error(f"GitLab API error getting project members: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting project members: {e}")
            return None
    
    def _get_user_id(self, username: str) -> Optional[int]:
        """
        Get GitLab user ID from username.
        
        Args:
            username: GitLab username
            
        Returns:
            User ID or None if not found
        """
        try:
            users = self.gl.users.list(username=username)
            if users:
                return users[0].id
            else:
                self.logger.error(f"User not found: {username}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting user ID for {username}: {e}")
            return None
    
    def validate_assignee(self, project_path: str, username: str) -> bool:
        """
        Validate that a user can be assigned to issues in the project.
        
        Args:
            project_path: GitLab project path
            username: Username to validate
            
        Returns:
            True if user can be assigned, False otherwise
        """
        try:
            # Get project members
            members = self.get_project_members(project_path)
            if not members:
                return False
            
            # Check if username is in project members
            member_usernames = [member['username'] for member in members]
            is_member = username in member_usernames
            
            if is_member:
                self.logger.info(f"User {username} is a valid assignee for project {project_path}")
            else:
                self.logger.warning(f"User {username} is not a member of project {project_path}")
            
            return is_member
            
        except Exception as e:
            self.logger.error(f"Error validating assignee {username}: {e}")
            return False
    
    def health_check(self) -> bool:
        """
        Check if GitLab connection is working.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            # Try to get current user info
            user = self.gl.user
            if user:
                self.logger.info(f"GitLab health check passed (user: {user.username})")
                return True
            else:
                self.logger.error("GitLab health check failed: no user info")
                return False
                
        except Exception as e:
            self.logger.error(f"GitLab health check failed: {e}")
            return False
    
    def process_reassignment(self, issue_url: str, new_assignee: str, ai_reasoning: str = None) -> bool:
        """
        Complete workflow to reassign an issue and add explanatory comment.
        
        Args:
            issue_url: GitLab issue URL
            new_assignee: New assignee username
            ai_reasoning: AI reasoning for the assignment (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Parse issue URL
            parsed = self.parse_issue_url(issue_url)
            if not parsed:
                return False
            
            project_path, issue_iid = parsed
            
            # Validate assignee
            if not self.validate_assignee(project_path, new_assignee):
                self.logger.error(f"Cannot assign to {new_assignee}: not a project member")
                return False
            
            # Get current issue details
            current_issue = self.get_issue(project_path, issue_iid)
            if not current_issue:
                return False
            
            current_assignee = current_issue.get('assignee')
            
            # Check if reassignment is needed
            if current_assignee == new_assignee:
                self.logger.info(f"Issue {issue_iid} is already assigned to {new_assignee}")
                return True
            
            # Reassign the issue
            if not self.reassign_issue(project_path, issue_iid, new_assignee):
                return False
            
            # Add explanatory comment
            comment_parts = [
                f"🤖 **Automated Assignment Update**",
                f"",
                f"This issue has been reassigned from `{current_assignee or 'unassigned'}` to `{new_assignee}` based on AI analysis."
            ]
            
            if ai_reasoning:
                comment_parts.extend([
                    f"",
                    f"**AI Reasoning:**",
                    f"{ai_reasoning}"
                ])
            
            comment_parts.extend([
                f"",
                f"---",
                f"*This assignment was made automatically by the mailbox-monitor service.*"
            ])
            
            comment = "\n".join(comment_parts)
            self.add_issue_comment(project_path, issue_iid, comment)
            
            self.logger.info(f"Successfully processed reassignment of issue {issue_iid} to {new_assignee}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing reassignment: {e}")
            return False