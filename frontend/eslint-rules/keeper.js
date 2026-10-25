/**
 * Keeper's local ESLint rules (docs/10-build/03-testing-strategy.md §6).
 * - no-literal-copy: JSX text and string-literal title/label/placeholder/aria-label/alt props must come from t().
 * - no-fixed-px: class strings must not use fixed px sizes (1px and 2px borders/rings are allowed) or raw hex colours.
 */
const COPY_PROPS = new Set(["title", "label", "placeholder", "aria-label", "alt", "aria-description", "description"]);
const LETTERS = /[A-Za-z]/;

function isClassAttr(name) {
  return name === "className" || name === "class";
}

const PX_RE = /(?:^|[\s:[(\-])(?:[a-z-]*-)?\[?[^\s\]]*?(\d+(?:\.\d+)?)px/g;
const HEX_RE = /\[#[0-9a-fA-F]{3,8}\]/;

function checkClassString(context, node, value) {
  if (typeof value !== "string") return;
  if (HEX_RE.test(value)) context.report({ node, messageId: "hex" });
  for (const m of value.matchAll(/(\d+(?:\.\d+)?)px/g)) {
    const n = Number(m[1]);
    if (n > 2) {
      context.report({ node, messageId: "px", data: { value: m[0] } });
      break;
    }
  }
}

const noLiteralCopy = {
  meta: {
    type: "problem",
    messages: {
      text: "User-facing text must come from t() (copy/en.json), not a JSX literal: “{{text}}”.",
      prop: "The {{prop}} prop must come from t() (copy/en.json), not a string literal.",
    },
    schema: [],
  },
  create(context) {
    return {
      JSXText(node) {
        const text = node.value.trim();
        if (text && LETTERS.test(text)) context.report({ node, messageId: "text", data: { text: text.slice(0, 40) } });
      },
      JSXAttribute(node) {
        const name = node.name && node.name.name;
        if (typeof name !== "string" || !COPY_PROPS.has(name)) return;
        const v = node.value;
        if (!v) return;
        const literal = v.type === "Literal" ? v.value : v.type === "JSXExpressionContainer" && v.expression.type === "Literal" ? v.expression.value : v.type === "JSXExpressionContainer" && v.expression.type === "TemplateLiteral" && v.expression.expressions.length === 0 ? v.expression.quasis[0].value.cooked : null;
        if (typeof literal === "string" && LETTERS.test(literal)) context.report({ node, messageId: "prop", data: { prop: name } });
      },
    };
  },
};

const noFixedPx = {
  meta: {
    type: "problem",
    messages: {
      px: "Fixed pixel sizes ({{value}}) are not allowed in class strings; use rem tokens, clamp() or container queries.",
      hex: "Raw hex colours are not allowed in class strings; use design tokens.",
    },
    schema: [],
  },
  create(context) {
    return {
      JSXAttribute(node) {
        const name = node.name && node.name.name;
        if (typeof name !== "string" || !isClassAttr(name) || !node.value) return;
        const v = node.value;
        if (v.type === "Literal") checkClassString(context, node, v.value);
        else if (v.type === "JSXExpressionContainer") {
          const e = v.expression;
          if (e.type === "Literal") checkClassString(context, node, e.value);
          if (e.type === "TemplateLiteral") for (const q of e.quasis) checkClassString(context, node, q.value.cooked);
        }
      },
      // cx("…", …) calls and *Class helpers
      CallExpression(node) {
        const callee = node.callee;
        const name = callee.type === "Identifier" ? callee.name : null;
        if (name !== "cx") return;
        for (const arg of node.arguments) {
          if (arg.type === "Literal") checkClassString(context, arg, arg.value);
          if (arg.type === "LogicalExpression" && arg.right.type === "Literal") checkClassString(context, arg.right, arg.right.value);
          if (arg.type === "ConditionalExpression") {
            if (arg.consequent.type === "Literal") checkClassString(context, arg.consequent, arg.consequent.value);
            if (arg.alternate.type === "Literal") checkClassString(context, arg.alternate, arg.alternate.value);
          }
        }
      },
    };
  },
};

export default { rules: { "no-literal-copy": noLiteralCopy, "no-fixed-px": noFixedPx } };
