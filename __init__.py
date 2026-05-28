"""
JLCPCB Auth plugin entry point.
"""

from .hooks import post_tool_call
from .schemas import JLCPCB_AUTH_STATUS, JLCPCB_LOGIN, JLCPCB_LOGOUT
from .tools import jlcpcb_auth_status, jlcpcb_login, jlcpcb_logout


def register(ctx):
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

    ctx.register_hook("post_tool_call", post_tool_call)

    if hasattr(ctx, "register_dashboard_plugin"):
        dashboard_dir = ctx.plugin_dir / "dashboard"
        if dashboard_dir.exists():
            try:
                ctx.register_dashboard_plugin(
                    name="jlcpcb-auth",
                    plugin_dir=dashboard_dir,
                )
            except Exception:
                ctx.register_dashboard_plugin(
                    name="jlcpcb-auth",
                    plugin_dir=ctx.plugin_dir,
                )

    ctx.register_skill(
        name="jlcpcb-auth",
        path=ctx.plugin_dir / "SKILL.md",
    )
