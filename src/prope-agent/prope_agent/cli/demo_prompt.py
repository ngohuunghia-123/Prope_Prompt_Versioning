"""Built-in demo prompt.

The demo command uses this string. It is intentionally weak — no role
statement, no constraints, no format guidance — so the optimizer has
visible work to do.
"""
DEMO_PROMPT = """\
You are a customer support assistant. You answer questions about orders, \
refunds, and shipping. Be friendly and helpful.
"""
