"""
OpenCode Server Client
Handles communication with OpenCode Server HTTP API
"""

import aiohttp
import json
from typing import Optional, Dict, Any, List, Union
import asyncio


class OpenCodeClient:
    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = None
        if username and password:
            self.auth = aiohttp.BasicAuth(username, password)
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make HTTP request to OpenCode Server"""
        if not self.session:
            raise Exception("Client not initialized. Use async with context.")

        url = f"{self.base_url}{endpoint}"

        try:
            async with self.session.request(
                method,
                url,
                auth=self.auth,
                timeout=aiohttp.ClientTimeout(total=None),
                **kwargs,
            ) as response:
                if response.status == 204:
                    return None
                if response.status >= 400:
                    text = await response.text()
                    raise Exception(f"HTTP {response.status}: {text}")

                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    return await response.json()
                return await response.text()
        except asyncio.TimeoutError:
            raise Exception("Request timed out (OpenCode Server may be busy)")
        except Exception as e:
            raise Exception(f"Request failed: {str(e)}")

    # ============ Health Check ============
    async def health_check(self) -> Dict[str, Any]:
        """Check if server is healthy"""
        return await self._request("GET", "/global/health")

    # ============ Sessions ============
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions"""
        return await self._request("GET", "/session")

    async def create_session(self, title: Optional[str] = None) -> Dict[str, Any]:
        """Create a new session"""
        body = {}
        if title:
            body["title"] = title
        return await self._request("POST", "/session", json=body)

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get session details"""
        return await self._request("GET", f"/session/{session_id}")

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        return await self._request("DELETE", f"/session/{session_id}")

    # ============ Messages ============
    async def send_message(
        self,
        session_id: str,
        content: str,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        no_reply: bool = False,
    ) -> Dict[str, Any]:
        """
        Send a message to a session and get response

        Args:
            session_id: Session ID
            content: Message content
            agent: Optional agent to use
            model: Optional model to use
            no_reply: If True, don't wait for response
        """
        body: Dict[str, Any] = {
            "parts": [{"type": "text", "text": content}],
            "noReply": no_reply,
        }
        if agent:
            body["agent"] = agent
        if model:
            # Model 应该是对象格式，使用 providerID 和 modelID
            provider_id, model_id = model.split("/", 1) if "/" in model else (model, model)
            body["model"] = {"providerID": provider_id, "modelID": model_id}

        return await self._request("POST", f"/session/{session_id}/message", json=body)

    async def send_message_async(
        self,
        session_id: str,
        content: str,
        agent: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Send message asynchronously (no wait for response)"""
        body: Dict[str, Any] = {
            "parts": [{"type": "text", "text": content}],
        }
        if agent:
            body["agent"] = agent
        if model:
            # Model 应该是对象格式，使用 providerID 和 modelID
            provider_id, model_id = model.split("/", 1) if "/" in model else (model, model)
            body["model"] = {"providerID": provider_id, "modelID": model_id}

        await self._request("POST", f"/session/{session_id}/prompt_async", json=body)

    async def list_messages(
        self, session_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """List messages in a session"""
        params = {}
        if limit:
            params["limit"] = limit
        return await self._request(
            "GET", f"/session/{session_id}/message", params=params
        )

    async def get_message(self, session_id: str, message_id: str) -> Dict[str, Any]:
        """Get specific message details"""
        return await self._request("GET", f"/session/{session_id}/message/{message_id}")

    # ============ Commands ============
    async def execute_command(
        self,
        session_id: str,
        command: str,
        arguments: Optional[List[str]] = None,
        agent: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a slash command"""
        body: Dict[str, Any] = {"command": command}
        if arguments:
            body["arguments"] = arguments
        if agent:
            body["agent"] = agent
        if model:
            # Model 应该是对象格式，使用 providerID 和 modelID
            provider_id, model_id = model.split("/", 1) if "/" in model else (model, model)
            body["model"] = {"providerID": provider_id, "modelID": model_id}

        return await self._request("POST", f"/session/{session_id}/command", json=body)

    # ============ Files ============
    async def list_files(self, path: str = "") -> List[Dict[str, Any]]:
        """List files and directories"""
        params = {"path": path} if path else {}
        return await self._request("GET", "/file", params=params)

    async def read_file(self, path: str) -> Dict[str, Any]:
        """Read file content"""
        return await self._request("GET", "/file/content", params={"path": path})

    async def find_files(self, query: str) -> List[str]:
        """Find files by name"""
        return await self._request("GET", "/find/file", params={"query": query})

    async def search_text(self, pattern: str) -> List[Dict[str, Any]]:
        """Search for text in files"""
        return await self._request("GET", "/find", params={"pattern": pattern})

    # ============ Session Control ============
    async def abort_session(self, session_id: str) -> bool:
        """Abort running session"""
        return await self._request("POST", f"/session/{session_id}/abort")

    async def revert_message(self, session_id: str, message_id: str) -> bool:
        """Revert a message"""
        return await self._request(
            "POST", f"/session/{session_id}/revert", json={"messageID": message_id}
        )

    async def unrevert_messages(self, session_id: str) -> bool:
        """Restore all reverted messages"""
        return await self._request("POST", f"/session/{session_id}/unrevert")

    async def get_diff(
        self, session_id: str, message_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get diff for session"""
        params = {}
        if message_id:
            params["messageID"] = message_id
        return await self._request("GET", f"/session/{session_id}/diff", params=params)