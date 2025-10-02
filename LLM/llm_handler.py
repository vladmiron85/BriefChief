import logging
import os
import traceback
from typing import Dict, List, Optional

from langchain.agents import AgentType, initialize_agent
from langchain.schema import HumanMessage, SystemMessage
from langchain.tools import StructuredTool
from langchain_openai import ChatOpenAI

from .jira_tools import create_jira_langchain_tools, get_user_jira_credentials

logger = logging.getLogger(__name__)

PROMPT_FILE_USER = "LLM/prompt_user.txt"
PROMPT_FILE_SYSTEM = "LLM/prompt_system.txt"
SYSTEM_PROMPT_DEFAULT = "You are an AI assistant specialized in analyzing chat conversations and identifying task agreements."

def load_prompt_from_file(filename: str = PROMPT_FILE_SYSTEM) -> str:
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

def get_available_models() -> Dict[str, str]:
    return {"model_openai": "OpenAI"}

def collect_tools(telegram_user_id: Optional[str] = None) -> List[StructuredTool]:
    tools = []
    
    if not telegram_user_id:
        logger.info("No telegram_user_id provided, no tools available")
        return tools
    
    try:
        logger.info(f"Getting Jira credentials for user {telegram_user_id}...")
        if credentials := get_user_jira_credentials(telegram_user_id):
            logger.info(f"📋 Creating Jira tools with OAuth 2.0 Bearer token")
            logger.info(f"   URL: {credentials['jira_url']}")
            
            jira_tools = create_jira_langchain_tools(
                jira_url=credentials['jira_url'],
                cloud_id=credentials['jira_cloud_id'],
                access_token=credentials['jira_token']
            )
            tools.extend(jira_tools)
            logger.info(f"✅ Successfully created {len(jira_tools)} Jira tools")
        else:
            logger.warning("Could not get user credentials, no Jira tools available")
    except Exception as e:
        logger.warning(f"Jira tools not available: {e}")
        logger.warning(f"Traceback: {traceback.format_exc()}")
    
    return tools

async def call_llm(messages: str, llm_choice: str = "model_openai", tools: Optional[List[StructuredTool]] = None) -> str:
    if llm_choice not in get_available_models():
        return f"Unknown LLM choice: {llm_choice}. Available options: {', '.join(get_available_models().keys())}"

    if tools is None:
        tools = []
    
    try:
        system_prompt = load_prompt_from_file(PROMPT_FILE_SYSTEM) or SYSTEM_PROMPT_DEFAULT
        user_prompt = load_prompt_from_file(PROMPT_FILE_USER)
        
        logger.info(f"System prompt: {system_prompt}")
        langchain_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt + messages)
        ]
        
        llm = ChatOpenAI(model="gpt-4o", max_tokens=8000)
        logger.info("Initialized OpenAI LLM")

        if tools:
            logger.info(f"Initializing LangChain agent with {len(tools)} tools...")
            agent = initialize_agent(
                tools=tools,
                llm=llm,
                agent=AgentType.OPENAI_FUNCTIONS,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=10,
                return_intermediate_steps=False
            )
            logger.info("Running agent with tools...")
            response = await agent.arun(langchain_messages[-1].content)
            logger.info("Agent completed successfully")
        else:
            logger.info("Using basic LLM without tools...")
            response = await llm.ainvoke(langchain_messages)
            response = response.content
            logger.info("Basic LLM completed successfully")
        
        return response
    except Exception as e:
        logger.error(f"Error calling LLM: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return f"Error calling LLM: {str(e)}"

async def handle_llm_command(messages: str, llm_choice: str = "model_openai", telegram_user_id: Optional[str] = None) -> tuple[str, bool]:
    if not messages or messages == "No new messages since last call.":
        return "No new messages since last call.", False
    
    try:
        tools = collect_tools(telegram_user_id)
        response = await call_llm(messages, llm_choice, tools)
        return f"Found task agreements:\n\n{response}", True
    except Exception as e:
        logger.error(f"Error processing messages with LLM: {e}")
        return f"Error processing messages: {str(e)}", False
