"""
__init__.py — JLCPCB Auth plugin entry point.

Registers:
  - Three tools: jlcpcb_login, jlcpcb_logout, jlcpcb_auth_status
  - One hook: post_tool_call (credential redaction)
  - One dashboard UI plugin: JLCPCB Credentials panel
  - One skill: jlcpcb-auth (guides the model on when to call these tools)
"""

from .schemas import JLCPCB_LOGIN, JLCPCB_LOGOUT, JLCPCB_AUTH_STATUS
from .tools import jlcpcb_login, jlcpcb_logout, jlcpcb_auth_status
from .hooks import post_tool_call


def register(ctx):
    # ------------------------------------------------------------------
    # Tools — model can call these, no credential parameters on any of them
    # ------------------------------------------------------------------
    ctx.register_tool(
        name="jlcpcb_login",
        schema=JLCPCB_LOGIN,
        handler=jlcpcb_login,
    )
    ctx.register_tool(
        name="jlcpcb_logout",
        schema=JLCPCB_LOGOUT,
        handler=jlcpcb_logout,
    )
    ctx.register_tool(
        name="jlcpcb_auth_status",
        schema=JLCPCB_AUTH_STATUS,
        handler=jlcpcb_auth_status,
    )

    # ------------------------------------------------------------------
    # Hook — post_tool_call runs after every tool call in the session,
    # redacting any accidental credential leaks before the model sees them
    # ------------------------------------------------------------------
    ctx.register_hook("post_tool_call", post_tool_call)

    # ------------------------------------------------------------------
    # Dashboard UI plugin — credentials management panel
    # ------------------------------------------------------------------
    ctx.register_dashboard_plugin(
        name="jlcpcb-auth",
        plugin_dir=ctx.plugin_dir,  # points to this plugin's directory
    )

    # ------------------------------------------------------------------
    # Skill — loaded on demand with /jlcpcb-auth or skill_view("jlcpcb-auth")
    # ------------------------------------------------------------------
    ctx.register_skill(
        name="jlcpcb-auth",
        path=ctx.plugin_dir / "SKILL.md",
    )
