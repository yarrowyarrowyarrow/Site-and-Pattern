"""
mcp_server.py — MCP (Model Context Protocol) server for PermaDesign.

Exposes plant search, guild browsing, and design session management as MCP
tools so AI agents can generate permaculture designs without the Qt GUI.

Usage:
    python -m permadesign mcp

Configure in Claude Code (~/.claude.json or project .claude.json):
    {
      "mcpServers": {
        "permadesign": { "command": "python", "args": ["-m", "permadesign", "mcp"] }
      }
    }
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from src.bootstrap import bootstrap_db
from src.design_api import DesignGenerator

# In-process session store: session_id → DesignGenerator
_sessions: dict[str, DesignGenerator] = {}

server = Server("permadesign")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_plants",
            description="Search the plant catalogue by zone, sun, water needs, type, and other filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query":          {"type": "string",  "description": "Free-text search (name, scientific name, uses)"},
                    "plant_type":     {"type": "string",  "description": "tree|shrub|herb|groundcover|vine|grass|aquatic"},
                    "sun_req":        {"type": "string",  "description": "full|partial|shade"},
                    "water_needs":    {"type": "string",  "description": "low|moderate|high"},
                    "zone":           {"type": "integer", "description": "USDA hardiness zone number (e.g. 3)"},
                    "native_only":    {"type": "boolean"},
                    "edible_only":    {"type": "boolean"},
                    "pollinator_only":{"type": "boolean"},
                    "nfixer_only":    {"type": "boolean"},
                    "perennial_only": {"type": "boolean"},
                },
            },
        ),
        types.Tool(
            name="get_plant_details",
            description="Get full plant record including companion relationships.",
            inputSchema={
                "type": "object",
                "required": ["plant_id"],
                "properties": {
                    "plant_id": {"type": "integer"},
                },
            },
        ),
        types.Tool(
            name="list_guilds",
            description="List all seeded polyculture guilds (companion planting communities).",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_guild_details",
            description="Get a guild's full member list with spacing offsets and roles.",
            inputSchema={
                "type": "object",
                "required": ["guild_id"],
                "properties": {
                    "guild_id": {"type": "integer"},
                },
            },
        ),
        types.Tool(
            name="list_saved_recipes",
            description="List user-saved polyculture mix recipes.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="create_design",
            description="Start a new design session. Returns a session_id for subsequent calls.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name":           {"type": "string"},
                    "latitude":       {"type": "number"},
                    "longitude":      {"type": "number"},
                    "hardiness_zone": {"type": "string"},
                    "area_m2":        {"type": "number"},
                    "soil_type":      {"type": "string"},
                    "sun_exposure":   {"type": "string"},
                },
            },
        ),
        types.Tool(
            name="add_plant",
            description="Place a plant at lat/lng in a design session.",
            inputSchema={
                "type": "object",
                "required": ["session_id", "plant_id", "lat", "lng"],
                "properties": {
                    "session_id": {"type": "string"},
                    "plant_id":   {"type": "integer"},
                    "lat":        {"type": "number"},
                    "lng":        {"type": "number"},
                    "quantity":   {"type": "integer", "default": 1},
                },
            },
        ),
        types.Tool(
            name="add_guild",
            description="Place a full guild (polyculture community) centred at lat/lng in a design session.",
            inputSchema={
                "type": "object",
                "required": ["session_id", "guild_id", "lat", "lng"],
                "properties": {
                    "session_id": {"type": "string"},
                    "guild_id":   {"type": "integer"},
                    "lat":        {"type": "number"},
                    "lng":        {"type": "number"},
                },
            },
        ),
        types.Tool(
            name="validate_design",
            description="Validate a design session and return any warnings or errors.",
            inputSchema={
                "type": "object",
                "required": ["session_id"],
                "properties": {
                    "session_id": {"type": "string"},
                },
            },
        ),
        types.Tool(
            name="export_design",
            description="Export a design session as a GeoJSON string.",
            inputSchema={
                "type": "object",
                "required": ["session_id"],
                "properties": {
                    "session_id": {"type": "string"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    try:
        result = _dispatch(name, arguments)
    except KeyError as exc:
        result = {"error": f"Unknown session or missing argument: {exc}"}
    except Exception as exc:
        result = {"error": str(exc)}
    return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


def _dispatch(name: str, args: dict[str, Any]) -> Any:
    if name == "search_plants":
        gen = DesignGenerator()
        return gen.search_plants(**args)

    if name == "get_plant_details":
        gen = DesignGenerator()
        return gen.get_plant_details(int(args["plant_id"]))

    if name == "list_guilds":
        gen = DesignGenerator()
        return gen.list_guilds()

    if name == "get_guild_details":
        gen = DesignGenerator()
        return gen.get_guild_details(int(args["guild_id"]))

    if name == "list_saved_recipes":
        gen = DesignGenerator()
        return gen.list_saved_recipes()

    if name == "create_design":
        session_id = str(uuid.uuid4())
        _sessions[session_id] = DesignGenerator(args or {})
        return {"session_id": session_id}

    if name == "add_plant":
        gen = _sessions[args["session_id"]]
        gen.add_plant(
            plant_id=int(args["plant_id"]),
            lat=float(args["lat"]),
            lng=float(args["lng"]),
            quantity=int(args.get("quantity", 1)),
        )
        return {"ok": True}

    if name == "add_guild":
        gen = _sessions[args["session_id"]]
        gen.add_guild(
            guild_id=int(args["guild_id"]),
            center_lat=float(args["lat"]),
            center_lng=float(args["lng"]),
        )
        return {"ok": True}

    if name == "validate_design":
        gen = _sessions[args["session_id"]]
        return gen.validate()

    if name == "export_design":
        gen = _sessions[args["session_id"]]
        return gen.get_project()

    raise ValueError(f"Unknown tool: {name!r}")


async def _main() -> None:
    bootstrap_db()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
