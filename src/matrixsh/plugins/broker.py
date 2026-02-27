"""Unified Tool Broker.

Provides a single interface for all tools (built-in + external plugins)
with central policy enforcement, namespacing, and access control.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, TYPE_CHECKING

from .connector import ToolInfo, ToolCallResult
from .manager import PluginManager
from .models import AgentProfile, PermissionLevel

if TYPE_CHECKING:
    from ..mcp.registry import ToolRegistry


# Built-in namespace for core MatrixShell tools
CORE_NAMESPACE = "core"


@dataclass
class UnifiedTool:
    """A tool in the unified catalog."""
    namespace: str
    name: str
    description: str = ""
    source: Literal["builtin", "plugin"] = "builtin"
    plugin_id: Optional[str] = None
    requires_confirmation: bool = True
    permission_level: PermissionLevel = PermissionLevel.READ
    input_schema: Dict[str, Any] = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        """Get fully qualified name."""
        return f"{self.namespace}.{self.name}"


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""
    allowed: bool
    reason: Optional[str] = None
    requires_confirmation: bool = False
    confirm_token: Optional[str] = None


@dataclass
class AuditEntry:
    """Audit log entry for tool calls."""
    timestamp: float
    tool_name: str
    namespace: str
    source: str
    agent_id: Optional[str]
    arguments: Dict[str, Any]
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None


class RateLimiter:
    """Simple rate limiter for tool calls."""

    def __init__(self):
        self._calls: Dict[str, List[float]] = defaultdict(list)

    def check(self, key: str, max_calls: int, window_seconds: float = 60.0) -> bool:
        """Check if a call is allowed under rate limits."""
        now = time.time()
        cutoff = now - window_seconds

        # Clean old entries
        self._calls[key] = [t for t in self._calls[key] if t > cutoff]

        if len(self._calls[key]) >= max_calls:
            return False

        self._calls[key].append(now)
        return True


class ToolBroker:
    """Central broker for all tool access.

    Responsibilities:
    - Unified tool catalog (built-in + plugins)
    - Namespace management
    - Policy enforcement
    - Rate limiting
    - Audit logging
    - Agent permission control
    """

    def __init__(
        self,
        registry: Optional["ToolRegistry"] = None,
        plugin_manager: Optional[PluginManager] = None,
    ):
        self._registry = registry
        self._plugin_manager = plugin_manager or PluginManager()
        self._tools: Dict[str, UnifiedTool] = {}
        self._rate_limiter = RateLimiter()
        self._audit_log: List[AuditEntry] = []
        self._max_audit_entries = 1000

        # Build initial catalog
        self._build_catalog()

    def _build_catalog(self) -> None:
        """Build unified tool catalog from all sources."""
        self._tools.clear()

        # Add built-in tools from registry
        if self._registry:
            self._add_builtin_tools()

        # Add tools from connected plugins
        self._add_plugin_tools()

    def _add_builtin_tools(self) -> None:
        """Add built-in tools from the ToolRegistry."""
        # Shell tools
        shell_tools = [
            ("shell_execute", "Execute a shell command", PermissionLevel.WRITE),
            ("shell_change_directory", "Change working directory", PermissionLevel.READ),
            ("shell_list_files", "List files in directory", PermissionLevel.READ),
            ("shell_get_system_info", "Get OS and shell information", PermissionLevel.READ),
        ]
        for name, desc, level in shell_tools:
            self._tools[f"{CORE_NAMESPACE}.{name}"] = UnifiedTool(
                namespace=CORE_NAMESPACE,
                name=name,
                description=desc,
                source="builtin",
                permission_level=level,
                requires_confirmation=level == PermissionLevel.WRITE,
            )

        # Safety tools
        safety_tools = [
            ("safety_classify_input", "Classify input as command or natural language", PermissionLevel.READ),
            ("safety_validate_command", "Check if command is safe", PermissionLevel.READ),
            ("safety_parse_shell_error", "Parse shell error messages", PermissionLevel.READ),
        ]
        for name, desc, level in safety_tools:
            self._tools[f"{CORE_NAMESPACE}.{name}"] = UnifiedTool(
                namespace=CORE_NAMESPACE,
                name=name,
                description=desc,
                source="builtin",
                permission_level=level,
                requires_confirmation=False,
            )

        # LLM tools
        llm_tools = [
            ("llm_suggest_command", "Get AI suggestion for shell command", PermissionLevel.READ),
            ("llm_health_check", "Check LLM gateway health", PermissionLevel.READ),
        ]
        for name, desc, level in llm_tools:
            self._tools[f"{CORE_NAMESPACE}.{name}"] = UnifiedTool(
                namespace=CORE_NAMESPACE,
                name=name,
                description=desc,
                source="builtin",
                permission_level=level,
                requires_confirmation=False,
            )

        # History tools
        history_tools = [
            ("history_append", "Log interaction to history", PermissionLevel.WRITE),
            ("history_load", "Load recent history", PermissionLevel.READ),
        ]
        for name, desc, level in history_tools:
            self._tools[f"{CORE_NAMESPACE}.{name}"] = UnifiedTool(
                namespace=CORE_NAMESPACE,
                name=name,
                description=desc,
                source="builtin",
                permission_level=level,
                requires_confirmation=False,
            )

        # Config tools
        config_tools = [
            ("config_get", "Get current configuration", PermissionLevel.READ),
            ("config_set", "Update configuration", PermissionLevel.ADMIN),
        ]
        for name, desc, level in config_tools:
            self._tools[f"{CORE_NAMESPACE}.{name}"] = UnifiedTool(
                namespace=CORE_NAMESPACE,
                name=name,
                description=desc,
                source="builtin",
                permission_level=level,
                requires_confirmation=level in (PermissionLevel.WRITE, PermissionLevel.ADMIN),
            )

    def _add_plugin_tools(self) -> None:
        """Add tools from all connected plugins."""
        for tool_info in self._plugin_manager.get_all_tools():
            full_name = tool_info.full_name
            plugin = None

            # Find the plugin this tool belongs to
            for p in self._plugin_manager.config.plugins:
                if p.namespace == tool_info.namespace:
                    plugin = p
                    break

            self._tools[full_name] = UnifiedTool(
                namespace=tool_info.namespace,
                name=tool_info.name,
                description=tool_info.description,
                source="plugin",
                plugin_id=plugin.id if plugin else None,
                requires_confirmation=plugin.permissions.requires_confirmation if plugin else True,
                permission_level=plugin.permissions.level if plugin else PermissionLevel.READ,
                input_schema=tool_info.input_schema,
            )

    def refresh_catalog(self) -> None:
        """Refresh the tool catalog."""
        self._build_catalog()

    def get_all_tools(self) -> List[UnifiedTool]:
        """Get all available tools."""
        return list(self._tools.values())

    def get_tool(self, full_name: str) -> Optional[UnifiedTool]:
        """Get a tool by its full name."""
        return self._tools.get(full_name)

    def get_tools_by_namespace(self, namespace: str) -> List[UnifiedTool]:
        """Get all tools in a namespace."""
        return [t for t in self._tools.values() if t.namespace == namespace]

    def get_namespaces(self) -> List[str]:
        """Get list of all namespaces."""
        return list(set(t.namespace for t in self._tools.values()))

    def evaluate_policy(
        self,
        full_name: str,
        arguments: Dict[str, Any],
        agent_profile: Optional[AgentProfile] = None,
    ) -> PolicyDecision:
        """Evaluate if a tool call is allowed.

        Checks:
        - Tool exists
        - Agent has permission (if agent_profile provided)
        - Rate limits
        - Namespace access
        """
        tool = self._tools.get(full_name)
        if not tool:
            return PolicyDecision(allowed=False, reason=f"Tool '{full_name}' not found")

        # Check agent permissions
        if agent_profile:
            # Check namespace access
            if agent_profile.denied_namespaces and tool.namespace in agent_profile.denied_namespaces:
                return PolicyDecision(allowed=False, reason=f"Namespace '{tool.namespace}' is denied for this agent")

            if agent_profile.allowed_namespaces and tool.namespace not in agent_profile.allowed_namespaces:
                return PolicyDecision(allowed=False, reason=f"Namespace '{tool.namespace}' is not allowed for this agent")

            # Check tool-level access
            if full_name in agent_profile.denied_tools:
                return PolicyDecision(allowed=False, reason=f"Tool '{full_name}' is denied for this agent")

            if agent_profile.allowed_tools and full_name not in agent_profile.allowed_tools:
                return PolicyDecision(allowed=False, reason=f"Tool '{full_name}' is not in agent's allowed list")

        # Check rate limits for plugin tools
        if tool.source == "plugin" and tool.plugin_id:
            plugin = self._plugin_manager.get_plugin(tool.plugin_id)
            if plugin and not self._rate_limiter.check(
                f"{tool.plugin_id}:{full_name}",
                plugin.permissions.max_calls_per_minute,
            ):
                return PolicyDecision(allowed=False, reason="Rate limit exceeded")

        # Determine if confirmation is required
        requires_confirmation = tool.requires_confirmation
        if agent_profile and agent_profile.requires_confirmation:
            requires_confirmation = True

        return PolicyDecision(
            allowed=True,
            requires_confirmation=requires_confirmation,
        )

    def call_tool(
        self,
        full_name: str,
        arguments: Dict[str, Any],
        agent_id: Optional[str] = None,
        skip_policy: bool = False,
    ) -> ToolCallResult:
        """Call a tool through the broker.

        All tool calls (built-in or plugin) should go through here.
        """
        tool = self._tools.get(full_name)
        if not tool:
            return ToolCallResult(success=False, error=f"Tool '{full_name}' not found")

        # Evaluate policy
        if not skip_policy:
            agent_profile = None
            if agent_id:
                agent_profile = next(
                    (a for a in self._plugin_manager.config.agents if a.id == agent_id),
                    None
                )

            decision = self.evaluate_policy(full_name, arguments, agent_profile)
            if not decision.allowed:
                self._log_audit(tool, arguments, agent_id, False, error=decision.reason)
                return ToolCallResult(success=False, error=decision.reason)

        # Route to appropriate handler
        try:
            if tool.source == "builtin":
                result = self._call_builtin_tool(tool, arguments)
            else:
                result = self._call_plugin_tool(tool, arguments)

            self._log_audit(tool, arguments, agent_id, result.success, result.result, result.error)
            return result

        except Exception as e:
            error = f"Tool call failed: {e}"
            self._log_audit(tool, arguments, agent_id, False, error=error)
            return ToolCallResult(success=False, error=error)

    def _call_builtin_tool(self, tool: UnifiedTool, arguments: Dict[str, Any]) -> ToolCallResult:
        """Call a built-in tool from the registry."""
        if not self._registry:
            return ToolCallResult(success=False, error="No registry available")

        try:
            # Map tool names to registry methods
            if tool.name == "shell_execute":
                result = self._registry.shell.execute(**arguments)
                return ToolCallResult(success=True, result=result)

            elif tool.name == "shell_change_directory":
                handled, new_cwd, error = self._registry.shell.handle_cd(
                    f"cd {arguments.get('path', '')}",
                    arguments.get("current_cwd", "."),
                )
                if handled and not error:
                    return ToolCallResult(success=True, result={"new_cwd": new_cwd})
                return ToolCallResult(success=False, error=error or "Failed to change directory")

            elif tool.name == "shell_list_files":
                files = self._registry.shell.list_files(
                    arguments.get("cwd", "."),
                    arguments.get("limit", 200),
                )
                return ToolCallResult(success=True, result={"files": files})

            elif tool.name == "shell_get_system_info":
                return ToolCallResult(success=True, result={
                    "os": self._registry.shell.os_name(),
                    "default_shell": self._registry.shell.default_mode(),
                })

            elif tool.name == "safety_classify_input":
                is_nl = self._registry.safety.looks_like_natural_language(arguments.get("text", ""))
                return ToolCallResult(success=True, result={"is_natural_language": is_nl})

            elif tool.name == "safety_validate_command":
                decision = self._registry.policy.evaluate(
                    arguments.get("cwd", "."),
                    arguments.get("command", ""),
                )
                return ToolCallResult(success=True, result=decision)

            elif tool.name == "llm_suggest_command":
                suggestion = self._registry.llm.suggest(
                    arguments.get("user_input", ""),
                    arguments.get("cwd", "."),
                )
                return ToolCallResult(success=True, result=suggestion)

            elif tool.name == "llm_health_check":
                health = self._registry.llm.health()
                return ToolCallResult(success=True, result=health)

            elif tool.name == "history_append":
                self._registry.history.append(
                    arguments.get("cwd", "."),
                    arguments.get("kind", "user"),
                    arguments.get("text", ""),
                )
                return ToolCallResult(success=True, result={"success": True})

            elif tool.name == "history_load":
                items = self._registry.history.load(
                    arguments.get("cwd", "."),
                    arguments.get("limit", 50),
                )
                return ToolCallResult(success=True, result={"items": [
                    {"ts": h.ts, "cwd": h.cwd, "kind": h.kind, "text": h.text}
                    for h in items
                ]})

            elif tool.name == "config_get":
                return ToolCallResult(success=True, result=self._registry.config.get())

            elif tool.name == "config_set":
                return ToolCallResult(success=True, result=self._registry.config.set(**arguments))

            else:
                return ToolCallResult(success=False, error=f"Unknown builtin tool: {tool.name}")

        except Exception as e:
            return ToolCallResult(success=False, error=str(e))

    def _call_plugin_tool(self, tool: UnifiedTool, arguments: Dict[str, Any]) -> ToolCallResult:
        """Call a tool from an external plugin."""
        if not tool.plugin_id:
            return ToolCallResult(success=False, error="Plugin ID not set for tool")

        return self._plugin_manager.call_tool(tool.plugin_id, tool.name, arguments)

    def _log_audit(
        self,
        tool: UnifiedTool,
        arguments: Dict[str, Any],
        agent_id: Optional[str],
        success: bool,
        result: Any = None,
        error: Optional[str] = None,
    ) -> None:
        """Log a tool call to the audit log."""
        entry = AuditEntry(
            timestamp=time.time(),
            tool_name=tool.name,
            namespace=tool.namespace,
            source=tool.source,
            agent_id=agent_id,
            arguments=arguments,
            success=success,
            result=result,
            error=error,
        )

        self._audit_log.append(entry)

        # Trim if too long
        if len(self._audit_log) > self._max_audit_entries:
            self._audit_log = self._audit_log[-self._max_audit_entries:]

    def get_audit_log(self, limit: int = 100) -> List[AuditEntry]:
        """Get recent audit log entries."""
        return self._audit_log[-limit:]

    # Plugin management passthrough
    @property
    def plugin_manager(self) -> PluginManager:
        return self._plugin_manager

    def connect_plugins(self) -> Dict[str, tuple]:
        """Connect all enabled plugins and refresh catalog."""
        results = self._plugin_manager.connect_all_enabled()
        self.refresh_catalog()
        return results

    def disconnect_plugins(self) -> None:
        """Disconnect all plugins."""
        self._plugin_manager.disconnect_all()
        self.refresh_catalog()
