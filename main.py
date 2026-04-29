from config import Config
from execution import run_once
from logger import init_logger
from mt5_client import Mt5Client

# TODO Fase 8: integrare ClaudeAgent
# from claude_agent import ClaudeAgent


def main() -> None:
    cfg = Config()
    logger = init_logger(cfg)
    mt5 = Mt5Client(cfg)

    if not mt5.initialize() or not mt5.login():
        logger.error("MT5 initialization/login failed: %s", "controllare credenziali in .env")
        return

    try:
        for symbol in cfg.SYMBOLS:
            account = mt5.get_account_state()
            logger.info(
                "Cycle start symbol=%s balance=%.2f equity=%.2f",
                symbol, account.balance, account.equity,
            )

            # TODO Fase 8: agent = ClaudeAgent(cfg, mt5, logger); proposal = agent.run_cycle(symbol, account)
            proposal = None

            if proposal is not None:
                run_once(symbol, proposal, cfg, mt5, logger)
            else:
                logger.info("NO_TRADE for %s (ClaudeAgent non ancora implementato — fase 8)", symbol)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
