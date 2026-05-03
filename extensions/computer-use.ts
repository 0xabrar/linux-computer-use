// Pi extension: registers slim Linux/X11 computer-use tools.
import type { ExtensionAPI, ToolDef, AgentToolResult } from "../src/types.ts";
import {
	listWindows, screenshot, click, typeText, setText, keypress, scroll, computerActions,
	ok, okWithImage, err, stopBridge,
} from "../src/bridge.ts";

// Plain JSON-schema params (kept terse for token efficiency).
const S = {
	listWindows: { type: "object", properties: {}, additionalProperties: false },
	screenshot: {
		type: "object",
		properties: { window: { type: "string", description: "@wN from list_windows" } },
		additionalProperties: false,
	},
	click: {
		type: "object",
		properties: {
			ref: { type: "string", description: "@eN or @wN" },
			x: { type: "number" }, y: { type: "number" },
			button: { type: "string", enum: ["left", "right", "middle"] },
			clickCount: { type: "number" },
		},
	},
	typeText: {
		type: "object",
		properties: { text: { type: "string" } },
		required: ["text"],
	},
	setText: {
		type: "object",
		properties: { ref: { type: "string" }, text: { type: "string" } },
		required: ["ref", "text"],
	},
	keypress: {
		type: "object",
		properties: { keys: { type: "array", items: { type: "string" }, minItems: 1 } },
		required: ["keys"],
	},
	scroll: {
		type: "object",
		properties: {
			ref: { type: "string" },
			x: { type: "number" }, y: { type: "number" },
			scrollY: { type: "number" }, scrollX: { type: "number" },
		},
	},
	computerActions: {
		type: "object",
		properties: { actions: { type: "array", minItems: 1, maxItems: 20 } },
		required: ["actions"],
	},
};

async function safe<T>(fn: () => Promise<T>): Promise<{ ok: true; v: T } | { ok: false; e: string }> {
	try { return { ok: true, v: await fn() }; }
	catch (e) { return { ok: false, e: e instanceof Error ? e.message : String(e) }; }
}

function fmtWindows(ws: any[]): string {
	return ws.map((w) => `${w.ref} pid=${w.pid} ${w.w}x${w.h}@${w.x},${w.y}${w.isFocused ? " *" : ""}  ${w.title}`).join("\n");
}

function fmtTargets(ts: any[]): string {
	if (!ts.length) return "(no AX targets)";
	return ts.slice(0, 60).map((t) => `${t.ref} ${t.role} "${t.name}" ${t.w}x${t.h}@${t.x},${t.y}`).join("\n");
}

const tools: ToolDef[] = [
	{
		name: "list_windows",
		description: "List X11 windows (@wN, title, pid, geometry, focus).",
		executionMode: "sequential",
		parameters: S.listWindows,
		async execute() {
			const r = await safe(() => listWindows());
			if (!r.ok) return err(r.e);
			const ws = (r.v as any).windows as any[];
			return ok(`${ws.length} windows:\n${fmtWindows(ws)}`, { windows: ws });
		},
	},
	{
		name: "screenshot",
		description: "Capture window (@wN) or full screen; returns AX targets and PNG.",
		executionMode: "sequential",
		parameters: S.screenshot,
		async execute(_id, p) {
			const r = await safe(() => screenshot({ window: p?.window }));
			if (!r.ok) return err(r.e);
			const v = r.v as any;
			const summary = `state=${v.stateId} ${v.width}x${v.height}\n${fmtTargets(v.axTargets)}`;
			return okWithImage(summary, v.pngBase64, { stateId: v.stateId, axTargets: v.axTargets });
		},
	},
	{
		name: "click",
		description: "Click by ref (@eN/@wN) or coordinates. button/clickCount optional.",
		executionMode: "sequential",
		parameters: S.click,
		async execute(_id, p) {
			const r = await safe(() => click(p ?? {}));
			return r.ok ? ok(`clicked`, r.v) : err(r.e);
		},
	},
	{
		name: "type_text",
		description: "Type text into the focused control.",
		executionMode: "sequential",
		parameters: S.typeText,
		async execute(_id, p) {
			const r = await safe(() => typeText({ text: p.text }));
			return r.ok ? ok(`typed ${(r.v as any).typed} chars`) : err(r.e);
		},
	},
	{
		name: "set_text",
		description: "Replace value of @eN text/entry (AT-SPI; falls back to focus+ctrl-a+type).",
		executionMode: "sequential",
		parameters: S.setText,
		async execute(_id, p) {
			const r = await safe(() => setText({ ref: p.ref, text: p.text }));
			return r.ok ? ok(`set (${(r.v as any).used})`) : err(r.e);
		},
	},
	{
		name: "keypress",
		description: 'Press keys, e.g. ["Enter"], ["Ctrl","A"], ["ctrl+l","Return"].',
		executionMode: "sequential",
		parameters: S.keypress,
		async execute(_id, p) {
			const r = await safe(() => keypress({ keys: p.keys }));
			return r.ok ? ok(`pressed`) : err(r.e);
		},
	},
	{
		name: "scroll",
		description: "Scroll at ref or x,y by scrollY/scrollX pixels (~40px/tick).",
		executionMode: "sequential",
		parameters: S.scroll,
		async execute(_id, p) {
			const r = await safe(() => scroll(p ?? {}));
			return r.ok ? ok(`scrolled`, r.v) : err(r.e);
		},
	},
	{
		name: "computer_actions",
		description: "Run a sequence of {click|type_text|set_text|keypress|scroll} actions.",
		executionMode: "sequential",
		parameters: S.computerActions,
		async execute(_id, p) {
			const r = await safe(() => computerActions({ actions: p.actions }));
			if (!r.ok) return err(r.e);
			const trace = (r.v as any).trace as any[];
			const lines = trace.map((t, i) => `${i}: ${t.type} ${t.ok ? "ok" : "fail: " + t.error}`);
			return ok(lines.join("\n"), { trace });
		},
	},
];

export default function computerUseExtension(pi: ExtensionAPI): void {
	for (const t of tools) {
		try { pi.registerTool(t); }
		catch (e) {
			if (!/conflicts with/.test(e instanceof Error ? e.message : "")) throw e;
		}
	}
	if (pi.on) pi.on("session_shutdown", () => stopBridge());
}
