"""
AI client module for predicting the correct assignee for GitLab issues.
Communicates with AI ticket assignment API.
"""

import requests
import logging
import json
from typing import Dict, Optional, List


class AIClient:
    """Client for AI ticket assignment API."""
    
    def __init__(self, api_url: str, api_key: Optional[str] = None, timeout: int = 30):
        """
        Initialize AI client.
        
        Args:
            api_url: Base URL for the AI API
            api_key: API key for authentication (optional)
            timeout: Request timeout in seconds
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        
        # Set up authentication headers
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            })
        else:
            self.session.headers.update({
                'Content-Type': 'application/json'
            })
    
    def predict_assignee(self, issue_data: Dict) -> Optional[Dict]:
        """
        Predict the best assignee for a GitLab issue.
        
        Args:
            issue_data: Dictionary containing issue information
                       Expected keys: title, description, labels, current_assignee, project
        
        Returns:
            Dictionary with prediction results or None if failed
            Expected format: {
                'recommended_assignee': str,
                'confidence': float,
                'reasoning': str,
                'alternatives': List[str]
            }
        """
        try:
            # Prepare request payload
            payload = self._prepare_prediction_payload(issue_data)
            
            # Make API request
            endpoint = f"{self.api_url}/predict-assignee"
            self.logger.info(f"Requesting assignee prediction for issue: {issue_data.get('title', 'Unknown')}")
            
            response = self.session.post(
                endpoint,
                json=payload,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            
            # Validate response format
            if self._validate_prediction_response(result):
                self.logger.info(f"AI prediction successful: {result.get('recommended_assignee')} "
                               f"(confidence: {result.get('confidence', 0):.2f})")
                return result
            else:
                self.logger.error("Invalid response format from AI API")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error calling AI API: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error from AI API response: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error calling AI API: {e}")
            return None
    
    def _prepare_prediction_payload(self, issue_data: Dict) -> Dict:
        """
        Prepare the payload for AI prediction request.
        
        Args:
            issue_data: Raw issue data from email
            
        Returns:
            Formatted payload for AI API
        """
        # Extract and clean the data
        payload = {
            'issue': {
                'title': issue_data.get('title', ''),
                'description': issue_data.get('description', ''),
                'labels': issue_data.get('labels', []),
                'current_assignee': issue_data.get('current_assignee', ''),
                'project': issue_data.get('project', ''),
                'url': issue_data.get('url', ''),
                'issue_number': issue_data.get('issue_number', '')
            }
        }
        
        # Add optional metadata
        if 'priority' in issue_data:
            payload['issue']['priority'] = issue_data['priority']
        
        if 'milestone' in issue_data:
            payload['issue']['milestone'] = issue_data['milestone']
            
        return payload
    
    def _validate_prediction_response(self, response: Dict) -> bool:
        """
        Validate the AI API response format.
        
        Args:
            response: Response dictionary from AI API
            
        Returns:
            True if response is valid, False otherwise
        """
        required_keys = ['recommended_assignee']
        
        # Check required keys
        for key in required_keys:
            if key not in response:
                self.logger.error(f"Missing required key in AI response: {key}")
                return False
        
        # Validate data types
        if not isinstance(response['recommended_assignee'], str):
            self.logger.error("recommended_assignee must be a string")
            return False
        
        # Check optional fields
        if 'confidence' in response and not isinstance(response['confidence'], (int, float)):
            self.logger.error("confidence must be a number")
            return False
        
        if 'alternatives' in response and not isinstance(response['alternatives'], list):
            self.logger.error("alternatives must be a list")
            return False
            
        return True
    
    def get_available_assignees(self, project: str = None) -> Optional[List[str]]:
        """
        Get list of available assignees for a project.
        
        Args:
            project: Project name or ID (optional)
            
        Returns:
            List of available assignee usernames or None if failed
        """
        try:
            endpoint = f"{self.api_url}/assignees"
            params = {}
            
            if project:
                params['project'] = project
            
            response = self.session.get(
                endpoint,
                params=params,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            if isinstance(result, dict) and 'assignees' in result:
                return result['assignees']
            elif isinstance(result, list):
                return result
            else:
                self.logger.error("Unexpected response format for assignees")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error getting assignees: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error getting assignees: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting assignees: {e}")
            return None
    
    def health_check(self) -> bool:
        """
        Check if the AI API is available and responding.
        
        Returns:
            True if API is healthy, False otherwise
        """
        try:
            endpoint = f"{self.api_url}/health"
            response = self.session.get(endpoint, timeout=self.timeout)
            
            if response.status_code == 200:
                self.logger.info("AI API health check passed")
                return True
            else:
                self.logger.warning(f"AI API health check failed with status: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"AI API health check failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error in AI API health check: {e}")
            return False
    
    def get_prediction_history(self, limit: int = 100) -> Optional[List[Dict]]:
        """
        Get recent prediction history from AI API.
        
        Args:
            limit: Maximum number of predictions to retrieve
            
        Returns:
            List of prediction records or None if failed
        """
        try:
            endpoint = f"{self.api_url}/predictions/history"
            params = {'limit': limit}
            
            response = self.session.get(
                endpoint,
                params=params,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            if isinstance(result, dict) and 'predictions' in result:
                return result['predictions']
            elif isinstance(result, list):
                return result
            else:
                self.logger.error("Unexpected response format for prediction history")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error getting prediction history: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error getting prediction history: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting prediction history: {e}")
            return None