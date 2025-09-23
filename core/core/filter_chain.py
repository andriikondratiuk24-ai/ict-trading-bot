from .filters import atr_filter, sweep_fractal, sweep_session, imb_tested, cisd_buy_sell

class FilterChain:
    def __init__(self, context):
        self.context = context
        self.filters = [
            self.atr_check,
            self.fractal_sweep_check,
            self.session_sweep_check,
            self.imb_check,
            self.cisd_check,
        ]

    def atr_check(self):
        return atr_filter(self.context["current_atr"], self.context["atr_min"], self.context["avg_atr_50"])

    def fractal_sweep_check(self):
        sweep_up, sweep_down = sweep_fractal(
            self.context["high"], self.context["low"],
            self.context["fractal_highs"], self.context["fractal_lows"], self.context["pip"]
        )
        self.context["sweep_fractal_up"] = sweep_up
        self.context["sweep_fractal_down"] = sweep_down
        return sweep_up or sweep_down

    def session_sweep_check(self):
        session_sweep_up, session_sweep_down = sweep_session(self.context)
        self.context["session_sweep_up"] = session_sweep_up
        self.context["session_sweep_down"] = session_sweep_down
        return session_sweep_up or session_sweep_down

    def imb_check(self):
        return imb_tested(self.context)

    def cisd_check(self):
        cisd_buy, cisd_sell = cisd_buy_sell(self.context)
        self.context["cisd_buy"] = cisd_buy
        self.context["cisd_sell"] = cisd_sell
        return cisd_buy or cisd_sell

    def run(self):
        for f in self.filters:
            if not f():
                return False
        return True
