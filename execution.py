import logging

import risk_engine
from config import Config
from logger import log_order_result, log_trade_decision
from models import RiskDecision, TradeProposal
from mt5_client import Mt5Client


def run_once(
    symbol: str,
    proposal: TradeProposal | None,
    cfg: Config,
    mt5_client: Mt5Client,
    logger: logging.Logger,
) -> RiskDecision | None:
    if proposal is None:
        return None

    account_state = mt5_client.get_account_state()
    decision = risk_engine.evaluate_trade(proposal, account_state, mt5_client, cfg)
    log_trade_decision(proposal, decision, account_state)

    if decision.approved and cfg.EXECUTION_MODE.lower() != "shadow":
        result = mt5_client.send_order(
            symbol,
            proposal.direction,
            decision.size_lots,
            decision.adjusted_stop_loss,
            decision.adjusted_take_profit,
            proposal.comment,
        )
        log_order_result(result, proposal)
        if result.success:
            logger.info(
                "Ordine inviato (%s) symbol=%s order_id=%s",
                cfg.EXECUTION_MODE, symbol, result.order_id,
            )
        else:
            logger.error(
                "Ordine fallito (%s) symbol=%s error=%s",
                cfg.EXECUTION_MODE, symbol, result.error_message,
            )

    return decision
