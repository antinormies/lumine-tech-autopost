from utils.finance_words import FINANCE_KEYWORDS, is_finance_related, compute_score


class TestIsFinanceRelated:
    def test_forex_text(self):
        assert is_finance_related("EUR/USD is looking bullish today")

    def test_stock_text(self):
        assert is_finance_related("Apple stock hit a new high")

    def test_crypto_text(self):
        assert is_finance_related("Bitcoin is crashing again")

    def test_indonesia_text(self):
        assert is_finance_related("IHSG menguat hari ini, saham perbankan naik")

    def test_trading_text(self):
        assert is_finance_related("Nice breakout on that support level")

    def test_non_finance_text(self):
        assert not is_finance_related("My cat is so cute today")

    def test_news_text(self):
        assert not is_finance_related("Breaking: earthquake hits the region")

    def test_sports_text(self):
        assert not is_finance_related("Indonesia beat Thailand 3-0 in the final")

    def test_empty_text(self):
        assert not is_finance_related("")

    def test_none_text(self):
        assert not is_finance_related(None)

    def test_tech_text(self):
        assert not is_finance_related("New iPhone announced with AI features")

    def test_boundary_investment(self):
        assert is_finance_related("long-term investment in renewable energy")

    def test_boundary_economy(self):
        assert is_finance_related("The economy is showing signs of recovery")


class TestComputeScore:
    def test_full_match(self):
        score = compute_score("forex trading stocks investment")
        assert score > 0.5

    def test_no_match(self):
        score = compute_score("cat dog bird")
        assert score == 0.0

    def test_partial_match(self):
        score = compute_score("I love trading cats")
        assert 0 < score < 1.0

    def test_empty_text(self):
        assert compute_score("") == 0.0


class TestFinanceKeywords:
    def test_keywords_exist(self):
        assert len(FINANCE_KEYWORDS) > 50

    def test_keywords_are_lowercase(self):
        for kw in FINANCE_KEYWORDS:
            assert kw == kw.lower(), f"Keyword '{kw}' is not lowercase"
