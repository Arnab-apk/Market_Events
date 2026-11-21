"""Model-facing task roles: filter, extraction and optional explanation. Each agent asks the model
client for one structured answer and then checks it against the source text. Agents never compute
scores; numerical evidence is decided later by fusion.py from market data.
"""
