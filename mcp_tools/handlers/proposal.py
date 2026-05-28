"""Proposal handlers per Phase 6 (D-C1, D-E1).

Tool inclusi (Wave 1):
- propose_trade (R3 — additive: setup_type + confluence_score D-C1)
- evaluate_trade_proposal (invariato; Phase 7/8 estendera' con ml_score/calibrated_prob)
- submit_order_if_approved (invariato)

R3 design (D-C1):
- args.context.{setup_type,confluence_score} valorizzati -> output li espone as-is
- args.context assente o incompleto -> output ha setup_type/confluence_score = None
  (freeform manual proposal flow). NON c'e' derivation automatica in Wave 1:
  Phase 4 evaluate_proposal_for_bar richiede StrategyContext + ProposalDraft,
  che lo skill costruisce upstream. Wave 1 si limita a propagare i valori
  forniti dal caller (D-C1 contract).

Riferimento: 06-CONTEXT.md D-C1, 06-RESEARCH.md R3.
"""
from __future__ import annotations

import dataclasses

from models import TradeProposal


def _build_proposal_from_args(args: dict, cfg) -> TradeProposal:
    """Costruisce TradeProposal validato dagli args del tool MCP."""
    timeframe = args.get("timeframe") or cfg.TIMEFRAME
    return TradeProposal(
        symbol=args["symbol"],
        direction=args["direction"],
        entry_price=float(args["entry_price"]),
        stop_loss_price=float(args["stop_loss_price"]),
        take_profit_price=float(args["take_profit_price"]),
        timeframe=timeframe,
        comment="mcp_propose_trade",
        confidence=float(args["confidence"]),
        rationale=args["rationale"],
    )


def handle_propose_trade(args: dict, log, cfg) -> dict:
    """R3 additive (D-C1): setup_type + confluence_score esposti come passthrough.

    Args:
        args: dict con i campi standard di propose_trade + opzionale 'context'
              {setup_type: "A"|"B"|"C"|"D", confluence_score: float}.
        log: logger.
        cfg: Config con TIMEFRAME default.

    Returns:
        dict con status, executed=False, proposal, setup_type, confluence_score,
        next_step. setup_type/confluence_score = None se context non li fornisce
        (freeform manual flow).
    """
    proposal = _build_proposal_from_args(args, cfg)
    log.info(
        "MCP propose_trade formalized: symbol=%s direction=%s confidence=%.2f",
        proposal.symbol, proposal.direction, proposal.confidence,
    )

    # R3 additive: estrazione da args.context (passthrough da skill upstream)
    setup_type = None
    confluence_score = None
    ctx_in = args.get("context") or {}
    if isinstance(ctx_in, dict):
        st = ctx_in.get("setup_type")
        if st in ("A", "B", "C", "D"):
            setup_type = st
        cs = ctx_in.get("confluence_score")
        if cs is not None:
            try:
                confluence_score = float(cs)
            except (TypeError, ValueError):
                # input malformed: log e degrade a None (Rule 1 difensivo)
                log.warning(
                    "R3 confluence_score malformed in context: %r -> None", cs,
                )

    return {
        "status": "proposed",
        "executed": False,
        "proposal": dataclasses.asdict(proposal),
        "setup_type": setup_type,                # additive D-C1 R3
        "confluence_score": confluence_score,    # additive D-C1 R3
        "next_step": (
            "call evaluate_trade_proposal or submit_order_if_approved "
            "to act on it"
        ),
    }


def handle_evaluate_trade_proposal(args: dict, mt5_client, cfg) -> dict:
    """Wave 1: invariato vs legacy. Phase 7/8 aggiungera' ml_score/calibrated_prob.

    Spostato verbatim da mcp_server.py dispatch (evaluate_trade_proposal branch).
    """
    from risk_engine import evaluate_trade

    proposal = _build_proposal_from_args(args, cfg)
    account = mt5_client.get_account_state()
    decision = evaluate_trade(proposal, account, mt5_client, cfg)
    return dataclasses.asdict(decision)


def handle_submit_order_if_approved(args: dict, mt5_client, cfg) -> dict:
    """Wave 1: invariato vs legacy.

    Spostato verbatim da mcp_server.py dispatch (submit_order_if_approved branch).
    """
    from execution import run_once

    proposal = _build_proposal_from_args(args, cfg)
    decision = run_once(proposal.symbol, proposal, cfg, mt5_client, None)
    return {
        "decision": dataclasses.asdict(decision) if decision is not None else None,
        "execution_mode": cfg.EXECUTION_MODE,
        "note": (
            "send_order eseguito solo se approved AND EXECUTION_MODE != shadow"
        ),
    }
