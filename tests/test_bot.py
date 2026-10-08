"""Offline tests for abecmed-watch.

Cover a phone-home script's pure logic: richText flattening, section
split/compare, state persistence, and the notification decision — all without
touching the ABECMED server or ntfy.
"""

import bot

# -------------------------------------------------------------- richText


def test_flatten_plain_text():
    assert bot.flatten({"text": "ola"}) == "ola"


def test_flatten_child_text():
    assert bot.flatten({"children": [{"text": "a"}, {"text": "b"}]}) == "ab"


def test_flatten_list_nodes():
    assert bot.flatten([{"text": "x"}, {"text": "y"}]) == "xy"


def test_flatten_non_dict_is_empty():
    assert bot.flatten("nada") == ""
    assert bot.flatten(42) == ""
    assert bot.flatten(None) == ""


def test_flatten_block_types_append_newline():
    for kind in ("p", "ul", "ol", "h1", "h2", "blockquote"):
        assert bot.flatten({"type": kind, "children": [{"text": "linha"}]}) == "linha\n"


def test_flatten_no_children_uses_text():
    assert bot.flatten({"type": "p"}) == ""


def test_flatten_li_prefix_dash():
    assert bot.flatten({"type": "li", "children": [{"text": "item"}]}) == "- item\n"


def test_flatten_nested_li():
    node = {"type": "li", "children": [{"text": "a "}, {"children": [{"text": "b"}]}]}
    assert bot.flatten(node) == "- a b\n"


def test_flatten_rich_mixed():
    node = {"type": "p", "children": [{"text": "Oi "}, {"text": "mundo"}]}
    assert bot.flatten(node) == "Oi mundo\n"


def test_messages_to_text_skips_non_rich():
    msgs = [{"content": {"type": "text", "text": "ignorado"}}]
    assert bot.messages_to_text(msgs) == ""


def test_messages_to_text_rich_only():
    msgs = [{"content": {"type": "richText", "richText": [{"children": [{"text": "vai"}]}]}}]
    assert bot.messages_to_text(msgs) == "vai"


def test_messages_to_text_media_url():
    msgs = [{"type": "image", "content": {"url": "https://ex/f.png"}}]
    assert bot.messages_to_text(msgs) == "[image] https://ex/f.png"


def test_tidy_trims_trailing_and_dup_blanks():
    text = "  a  \n\n\nb\t \n\n c "
    assert bot.tidy(text) == "a\n\nb\n\n c"


# -------------------------------------------------------------- sections


FLOR_SECAO = "== FLORES ==\nflor disponivel"
OLEO_SECAO = "== OLEO ==\noleo em falta"


def test_split_sections_empty():
    assert bot.split_sections("") == {}


def test_split_sections_two():
    report = FLOR_SECAO + "\n\n" + OLEO_SECAO
    assert bot.split_sections(report) == {"FLORES": "flor disponivel", "OLEO": "oleo em falta"}


def test_render_roundtrip_sections():
    sections = [("FLORES", "flor", ["Adquirir flor", "Adquirir oleo"]), ("OLEO", "oleo", [])]
    out = bot.render(sections)
    assert out.startswith("== FLORES ==")
    assert "opcoes: Adquirir flor | Adquirir oleo" in out
    assert "== OLEO ==" in out
    # round-trip: split recovers the same bodies
    parsed = bot.split_sections(out)
    assert parsed["FLORES"].startswith("flor")
    assert "oleo" in parsed["OLEO"]


def test_secoes_alteradas_new_section():
    old = FLOR_SECAO
    new = FLOR_SECAO + "\n\n" + OLEO_SECAO
    assert bot.secoes_alteradas(old, new) == ["OLEO"]


def test_secoes_alteradas_removed_section():
    old = FLOR_SECAO + "\n\n" + OLEO_SECAO
    new = FLOR_SECAO
    assert bot.secoes_alteradas(old, new) == ["OLEO"]


def test_secoes_alteradas_content_change():
    old = FLOR_SECAO + "\n\n" + OLEO_SECAO
    new = FLOR_SECAO + "\n\n== OLEO ==\noleo voltou"
    assert bot.secoes_alteradas(old, new) == ["OLEO"]


def test_secoes_alteradas_no_change():
    assert bot.secoes_alteradas(FLOR_SECAO, FLOR_SECAO) == []


def test_added_lines_only_new_content():
    old, new = "a\nb", "a\nb\nc"
    assert bot.added_lines(old, new) == ["c"]


def test_added_lines_removed_lines_not_reported():
    old, new = "a\nb\nc", "a\nc"
    assert bot.added_lines(old, new) == []


def test_added_lines_empty_base_is_full_diff():
    assert bot.added_lines("", "a\nb") == ["a", "b"]


# -------------------------------------------------------------- build_notification (novo)


def test_notif_first_run_seedling_priority3():
    title, body, tags, priority = bot.build_notification("", "== FLORES ==\nx")
    assert title == "abecmed-watch ativo"
    assert "== FLORES ==" in body
    assert tags == ["seedling"]
    assert priority == 3


def test_notif_flor_change_wakes_phone():
    old = "== FLORES ==\nsem estoque\n\n== OLEO ==\nok"
    new = "== FLORES ==\nflor nova\n\n== OLEO ==\nok"
    title, body, tags, priority = bot.build_notification(old, new)
    assert title == "Flor nova na ABECMED"
    assert tags == ["cherry_blossom", "rotating_light"]
    assert priority == 5


def test_notif_oleo_change_quiet_priority2():
    old = "== FLORES ==\nx\n\n== OLEO ==\nessgotado"
    new = "== FLORES ==\nx\n\n== OLEO ==\nvoltou"
    title, body, tags, priority = bot.build_notification(old, new)
    assert title == "ABECMED mudou: oleo"
    assert tags == ["bell"]
    assert priority == 2


def test_notif_no_prior_but_change_title_fallback():
    old = "== FLORES ==\nx"
    new = "== FLORES ==\nx\n\n== OLEO ==\ny"
    title, *_ = bot.build_notification(old, new)
    assert title == "ABECMED mudou: oleo"


def test_notif_destaque_lists_new_lines():
    old = "== FLORES ==\nx"
    new = "== FLORES ==\nx\nprogrediu"
    title, body, tags, priority = bot.build_notification(old, new)
    assert "Novidades:" in body
    assert "progrediu" in body
    assert title == "Flor nova na ABECMED"


# -------------------------------------------------------------- estado


def test_load_state_missing(tmp_path):
    assert bot.load_state(str(tmp_path / "nao_existe.json")) == {}


def test_load_state_corrupt(tmp_path):
    p = tmp_path / "estado.json"
    p.write_text("{{not json", encoding="utf-8")
    assert bot.load_state(str(p)) == {}


def test_save_load_roundtrip(tmp_path):
    p = tmp_path / "estado.json"
    bot.save_state(str(p), "== FLORES ==\nflor", quebrado=True)
    data = bot.load_state(str(p))
    assert data["report"] == "== FLORES ==\nflor"
    assert data["quebrado"] is True
    assert data["updated_at"]


def test_save_state_writes_trailing_newline(tmp_path):
    p = tmp_path / "estado.json"
    bot.save_state(str(p), "x")
    assert (p.read_text(encoding="utf-8")).endswith("\n")


def test_load_config_missing(tmp_path):
    assert bot.load_config(str(tmp_path / "ausente.ini")) == {}


def test_load_config_malformed(tmp_path):
    p = tmp_path / "bad.ini"
    p.write_text("[abecmed\ncpf = 123", encoding="utf-8")
    assert bot.load_config(str(p)) == {}


def test_load_config_no_abecmed_section(tmp_path):
    p = tmp_path / "x.ini"
    p.write_text("[outro]\ncpf = 9", encoding="utf-8")
    assert bot.load_config(str(p)) == {}


def test_load_config_parses_and_strips(tmp_path):
    p = tmp_path / "ok.ini"
    p.write_text("[abecmed]\ncpf =  123  \ntopico =  meu-canal ", encoding="utf-8")
    cfg = bot.load_config(str(p))
    assert cfg["cpf"] == "123"
    assert cfg["topico"] == "meu-canal"


# -------------------------------------------------------------- notify headeres


def test_post_json_strips_none_headers(monkeypatch):
    seen = {}

    class FakeResp:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(req, timeout):
        seen["headers"] = req.headers
        return FakeResp()

    monkeypatch.setattr(bot.urllib.request, "urlopen", fake_urlopen)
    bot.post_json("https://x", {"a": 1}, headers={"Origin": None, "X-Keep": "v"})
    keys = {k.lower() for k in seen["headers"]}
    assert "origin" not in keys
    assert seen["headers"]["X-keep"] == "v"
    assert "user-agent" in keys


def test_ciclo_dry_report_no_error(tmp_path):
    # sem rede: collect falha com FlowError, ciclo retorna True e marca quebrado
    ret = bot.ciclo("12345678901", "", str(tmp_path / "estado.json"))
    assert ret is True