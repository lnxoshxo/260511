from __future__ import annotations

import json
from pathlib import Path

from zipora.core.hotspots import (
    HotspotCollector,
    HotspotFetcher,
    HotspotRecord,
    HotspotSource,
    HotspotStore,
    load_sources,
    parse_hotspot_payload,
)


def test_parse_hotspot_payload_from_nested_json() -> None:
    source = HotspotSource(name="sample", url="https://example.com/hotspots.json")
    payload = {
        "data": {
            "items": [
                {
                    "plateName": "机器人",
                    "description": "产业政策催化，资金关注度提升",
                    "stockCode": "300001",
                    "stockName": "示例科技",
                    "score": "98.5",
                },
                {"plateName": "无归因"},
            ]
        }
    }

    records = parse_hotspot_payload(payload, source, observed_at="2026-05-12T00:00:00+00:00")

    assert len(records) == 1
    assert records[0].topic == "机器人"
    assert records[0].reason == "产业政策催化，资金关注度提升"
    assert records[0].symbol == "300001"
    assert records[0].symbol_name == "示例科技"
    assert records[0].heat == 98.5


def test_hotspot_store_deduplicates_and_exports(tmp_path: Path) -> None:
    store = HotspotStore(tmp_path / "hotspots.sqlite3")
    record = HotspotRecord(
        source="sample",
        source_url="https://example.com/hotspots.json",
        topic="算力",
        reason="模型需求拉动",
        symbol="000001",
        symbol_name="示例股份",
        heat=10.0,
        observed_at="2026-05-12T00:00:00+00:00",
        raw_json='{"topic":"算力"}',
    )

    assert store.save_records([record, record]) == 1
    assert store.save_records([record]) == 0
    assert store.list_records() == [record]

    exported = store.export_csv(tmp_path / "exports" / "hotspots.csv")

    assert exported == 1
    assert "模型需求拉动" in (tmp_path / "exports" / "hotspots.csv").read_text(encoding="utf-8")


def test_load_sources(tmp_path: Path) -> None:
    path = tmp_path / "sources.json"
    path.write_text(
        json.dumps([{"name": "sample", "url": "https://example.com/hotspots.json"}]),
        encoding="utf-8",
    )

    assert load_sources(path) == [
        HotspotSource(name="sample", url="https://example.com/hotspots.json")
    ]


def test_collector_uses_fetcher() -> None:
    class FakeFetcher(HotspotFetcher):
        def __init__(self) -> None:
            super().__init__()
            self.seen: list[HotspotSource] = []

        def fetch_json(self, source: HotspotSource):
            self.seen.append(source)
            return {"items": [{"topic": "AI", "reason": "应用落地加速"}]}

    source = HotspotSource(name="sample", url="https://example.com/hotspots.json")
    fetcher = FakeFetcher()

    records = HotspotCollector(fetcher).collect([source])

    assert fetcher.seen == [source]
    assert records[0].topic == "AI"
    assert records[0].reason == "应用落地加速"
