import json
import logging
import os
from typing import Callable, Dict, List, Optional

import requests
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

JIRA_AUTH_SERVER_URL = os.environ.get("JIRA_AUTH_SERVER_URL", "http://localhost:5000")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")


def get_user_jira_credentials(telegram_user_id: str) -> Optional[Dict]:
    if not INTERNAL_API_KEY:
        logger.error("INTERNAL_API_KEY not configured!")
        return None
    
    try:
        response = requests.get(
            f"{JIRA_AUTH_SERVER_URL}/auth/token/{telegram_user_id}",
            headers={'Authorization': f'Bearer {INTERNAL_API_KEY}'},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            access_token = data['access_token']
            cloud_id = data['jira_cloud_id']
            
            resources_response = requests.get(
                'https://api.atlassian.com/oauth/token/accessible-resources',
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=5
            )
            
            if resources_response.status_code == 200 and (resources := resources_response.json()):
                jira_resource = next((r for r in resources if r['id'] == cloud_id), resources[0])
                jira_url = jira_resource['url']
                
                logger.info(f"✅ Found Jira URL: {jira_url} for cloud_id: {cloud_id}")
                logger.info(f"   Resource name: {jira_resource.get('name', 'N/A')}")
                
                credentials = {
                    'jira_token': access_token,
                    'jira_username': data['jira_email'],
                    'jira_url': jira_url,
                    'jira_cloud_id': cloud_id
                }
                
                logger.info(f"✅ Returning credentials with URL: {credentials['jira_url']}")
                return credentials
            
            logger.error("Failed to get Jira URL from accessible resources")
        elif response.status_code == 401:
            logger.error("Unauthorized: Invalid API key")
        else:
            logger.error(f"Failed to get credentials: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error getting user credentials: {e}")
    return None


class JiraClient:
    
    def __init__(self, jira_url: str, cloud_id: str, access_token: str):
        self.jira_url = jira_url.rstrip('/')
        self.cloud_id = cloud_id
        self.access_token = access_token
        self.base_url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3"
        logger.info(f"Initialized Jira client for {self.jira_url} (cloud {self.cloud_id})")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        logger.debug(f"{method} {url}")
        
        try:
            response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
            response.raise_for_status()
            logger.debug(f"Response: {response.text}")
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            logger.error(f"Jira API error: {e}")
            if e.response:
                logger.error(f"Status: {e.response.status_code}, Response: {e.response.text}")
            error_msg = f"Jira API error: {e.response.status_code if e.response else 'Unknown'}"
            if e.response:
                error_msg += f" - {e.response.text}"
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise
    
    def search_issues(self, jql: str, fields: Optional[List[str]] = None, max_results: int = 50) -> Dict:
        logger.info(f"Searching Jira: {jql}")
        
        payload = {
            'jql': jql,
            'maxResults': max_results,
            'fields': fields or ['summary', 'status', 'assignee', 'reporter', 'priority', 'issuetype', 'created', 'updated']
        }
        
        result = self._make_request('POST', '/search/jql', json=payload)
        issues = result.get('issues', []) or []
        result['total'] = result.get('total') or len(issues)
        logger.info(f"Found {result['total']} issues")
        return result
    
    def get_issue(self, issue_key: str, fields: Optional[List[str]] = None) -> Dict:
        logger.info(f"Getting issue: {issue_key}")
        params = {'fields': ','.join(fields)} if fields else {}
        return self._make_request('GET', f'/issue/{issue_key}', params=params)
    
    def create_issue(self, project_key: str, summary: str, issue_type: str = "Task", 
                     description: Optional[str] = None, **kwargs) -> Dict:
        logger.info(f"Creating issue in {project_key}: {summary}")
        
        fields = {
            'project': {'key': project_key},
            'summary': summary,
            'issuetype': {'name': issue_type}
        }
        
        if description:
            fields['description'] = {
                'type': 'doc',
                'version': 1,
                'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': description}]}]
            }
        
        fields.update(kwargs)
        return self._make_request('POST', '/issue', json={'fields': fields})
    
    def update_issue(self, issue_key: str, fields: Dict) -> Dict:
        logger.info(f"Updating issue: {issue_key}")
        self._make_request('PUT', f'/issue/{issue_key}', json={'fields': fields})
        return {'success': True, 'key': issue_key}


def create_tool_wrapper(func: Callable, error_prefix: str) -> Callable:
    def wrapper(*args, **kwargs) -> str:
        try:
            result = func(*args, **kwargs)
            return json.dumps(result, indent=2, ensure_ascii=False) if isinstance(result, dict) else result
        except Exception as e:
            return f"{error_prefix}: {str(e)}"
    return wrapper


def create_jira_langchain_tools(jira_url: str, cloud_id: str, access_token: str) -> List[StructuredTool]:
    
    client = JiraClient(jira_url, cloud_id, access_token)
    
    class SearchIssuesInput(BaseModel):
        jql: str = Field(description="JQL query to search for issues. Examples: 'project = TestProject', 'assignee = currentUser()', 'status = \"In Progress\"'")
        max_results: int = Field(default=50, description="Maximum number of results to return (default: 50)")
    
    class GetIssueInput(BaseModel):
        issue_key: str = Field(description="Issue key (e.g., 'SMS-123', 'PROJ-456')")
    
    class CreateIssueInput(BaseModel):
        project_key: str = Field(description="Project key (e.g., 'SMS', 'PROJ')")
        summary: str = Field(description="Issue summary/title")
        issue_type: str = Field(default="Task", description="Issue type (Task, Bug, Story, etc.)")
        description: Optional[str] = Field(default=None, description="Issue description")
    
    def search_issues_tool(jql: str, max_results: int = 50) -> str:
        return create_tool_wrapper(
            lambda: client.search_issues(jql, max_results=max_results),
            "Error searching issues"
        )()
    
    def get_issue_tool(issue_key: str) -> str:
        return create_tool_wrapper(
            lambda: client.get_issue(issue_key),
            "Error getting issue"
        )()
    
    def create_issue_tool(project_key: str, summary: str, issue_type: str = "Task", description: Optional[str] = None) -> str:
        wrapper = create_tool_wrapper(
            lambda: client.create_issue(project_key, summary, issue_type, description),
            "Error creating issue"
        )
        result = wrapper()
        if result.startswith("Error"):
            return result
        
        try:
            issue_data = json.loads(result)
            issue_key = issue_data.get('key', 'Unknown')
            return f"Successfully created issue: {issue_key}\nSummary: {summary}"
        except:
            return result
    
    tools = [
        StructuredTool(
            name="search_jira_issues",
            description="Search for Jira issues using JQL (Jira Query Language). Use this to find issues by project, status, assignee, labels, etc.",
            func=search_issues_tool,
            args_schema=SearchIssuesInput
        ),
        StructuredTool(
            name="get_jira_issue",
            description="Get detailed information about a specific Jira issue by its key (e.g., SMS-123)",
            func=get_issue_tool,
            args_schema=GetIssueInput
        ),
        StructuredTool(
            name="create_jira_issue",
            description="Create a new Jira issue. Specify project key, summary, type (Task/Bug/Story), and optional description.",
            func=create_issue_tool,
            args_schema=CreateIssueInput
        )
    ]
    
    return tools
