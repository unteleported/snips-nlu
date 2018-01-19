# coding=utf-8
from __future__ import unicode_literals

import io
import json
import os
import traceback as tb
import unittest
from copy import deepcopy

from mock import patch

import snips_nlu
import snips_nlu.version
from snips_nlu.constants import DATA, TEXT, LANGUAGE, RES_INTENT, \
    RES_INTENT_NAME, RES_INPUT, RES_SLOTS, RES_MATCH_RANGE, RES_RAW_VALUE, \
    RES_VALUE, RES_ENTITY, RES_SLOT_NAME
from snips_nlu.dataset import validate_and_format_dataset
from snips_nlu.intent_parser.intent_parser import IntentParser, NotTrained
from snips_nlu.languages import Language
from snips_nlu.nlu_engine.nlu_engine import SnipsNLUEngine
from snips_nlu.nlu_engine.utils import enrich_slots, get_fitted_slot_filler, \
    add_fitted_slot_filler
from snips_nlu.pipeline.configs.config import ProcessingUnitConfig
from snips_nlu.pipeline.configs.intent_parser import \
    ProbabilisticIntentParserConfig
from snips_nlu.pipeline.configs.nlu_engine import NLUEngineConfig
from snips_nlu.pipeline.configs.slot_filler import CRFSlotFillerConfig
from snips_nlu.pipeline.units_registry import register_processing_unit, \
    reset_processing_units
from snips_nlu.result import parsing_result, _slot, \
    intent_classification_result, empty_result, custom_slot, resolved_slot
from snips_nlu.tests.utils import (
    SAMPLE_DATASET, get_empty_dataset, TEST_PATH, BEVERAGE_DATASET)


class TestSnipsNLUEngine(unittest.TestCase):
    def setUp(self):
        reset_processing_units()

    def test_should_use_parsers_sequentially(self):
        # Given
        input_text = "hello world"
        result = intent_classification_result(
            intent_name='dummy_intent_1', probability=0.7)
        slots = [_slot(match_range=(6, 11),
                       value='world',
                       entity='mocked_entity',
                       slot_name='mocked_slot_name')]

        class TestIntentParser1Config(ProcessingUnitConfig):
            unit_name = "test_intent_parser1"

            def to_dict(self):
                return {"unit_name": self.unit_name}

            @classmethod
            def from_dict(cls, obj_dict):
                return TestIntentParser1Config()

        class TestIntentParser1(IntentParser):
            unit_name = "test_intent_parser1"
            config_type = TestIntentParser1Config

            def fit(self, dataset, intents):
                return self

            def get_intent(self, text, intents=None):
                return None

            def get_slots(self, text, intent):
                return []

            def to_dict(self):
                return {
                    "unit_name": self.unit_name,
                }

            @classmethod
            def from_dict(cls, unit_dict):
                conf = cls.config_type()
                return TestIntentParser1(conf)

        class TestIntentParser2Config(ProcessingUnitConfig):
            unit_name = "test_intent_parser2"

            def to_dict(self):
                return {"unit_name": self.unit_name}

            @classmethod
            def from_dict(cls, obj_dict):
                return TestIntentParser2Config()

        class TestIntentParser2(IntentParser):
            unit_name = "test_intent_parser2"
            config_type = TestIntentParser2Config

            def fit(self, dataset, intents):
                return self

            def get_intent(self, text, intents=None):
                if text == input_text:
                    return result
                return None

            def get_slots(self, text, intent):
                if text == input_text:
                    return slots
                return []

            def to_dict(self):
                return {
                    "unit_name": self.unit_name,
                }

            @classmethod
            def from_dict(cls, unit_dict):
                conf = cls.config_type()
                return TestIntentParser2(conf)

        register_processing_unit(TestIntentParser1)
        register_processing_unit(TestIntentParser2)

        mocked_dataset_metadata = {
            "language_code": "en",
            "entities": {
                "mocked_entity": {
                    "automatically_extensible": True,
                    "utterances": dict()
                }
            },
            "slot_name_mappings": {
                "dummy_intent_1": {
                    "mocked_slot_name": "mocked_entity"
                }
            }
        }

        config = NLUEngineConfig([TestIntentParser1Config(),
                                  TestIntentParser2Config()])
        engine = SnipsNLUEngine(config).fit(SAMPLE_DATASET)
        engine.dataset_metadata = mocked_dataset_metadata

        # When
        parse = engine.parse(input_text)

        # Then
        expected_slots = [custom_slot(s) for s in slots]
        expected_parse = parsing_result(input_text, result, expected_slots)
        self.assertDictEqual(expected_parse, parse)

    def test_should_handle_empty_dataset(self):
        # Given
        dataset = validate_and_format_dataset(get_empty_dataset(Language.EN))
        engine = SnipsNLUEngine().fit(dataset)

        # When
        result = engine.parse("hello world")

        # Then
        self.assertEqual(empty_result("hello world"), result)

    def test_should_be_serializable(self):
        # Given
        class TestIntentParser1Config(ProcessingUnitConfig):
            unit_name = "test_intent_parser1"

            def to_dict(self):
                return {"unit_name": self.unit_name}

            @classmethod
            def from_dict(cls, obj_dict):
                return TestIntentParser1Config()

        class TestIntentParser1(IntentParser):
            unit_name = "test_intent_parser1"
            config_type = TestIntentParser1Config

            def fit(self, dataset, intents):
                return self

            def get_intent(self, text, intents=None):
                return None

            def get_slots(self, text, intent):
                return []

            def to_dict(self):
                return {
                    "unit_name": self.unit_name,
                }

            @classmethod
            def from_dict(cls, unit_dict):
                conf = cls.config_type()
                return TestIntentParser1(conf)

        class TestIntentParser2Config(ProcessingUnitConfig):
            unit_name = "test_intent_parser2"

            def to_dict(self):
                return {"unit_name": self.unit_name}

            @classmethod
            def from_dict(cls, obj_dict):
                return TestIntentParser2Config()

        class TestIntentParser2(IntentParser):
            unit_name = "test_intent_parser2"
            config_type = TestIntentParser2Config

            def fit(self, dataset, intents):
                return self

            def get_intent(self, text, intents=None):
                return None

            def get_slots(self, text, intent):
                return []

            def to_dict(self):
                return {
                    "unit_name": self.unit_name,
                }

            @classmethod
            def from_dict(cls, unit_dict):
                conf = cls.config_type()
                return TestIntentParser2(conf)

        register_processing_unit(TestIntentParser1)
        register_processing_unit(TestIntentParser2)

        parser1_config = TestIntentParser1Config()
        parser2_config = TestIntentParser2Config()
        parsers_configs = [parser1_config, parser2_config]
        config = NLUEngineConfig(parsers_configs)
        engine = SnipsNLUEngine(config).fit(BEVERAGE_DATASET)

        # When
        actual_engine_dict = engine.to_dict()

        # Then
        parser1_config = TestIntentParser1Config()
        parser2_config = TestIntentParser2Config()
        parsers_configs = [parser1_config, parser2_config]
        expected_engine_config = NLUEngineConfig(parsers_configs)
        expected_engine_dict = {
            "unit_name": "nlu_engine",
            "dataset_metadata": {
                "language_code": "en",
                "entities": {
                    "Temperature": {
                        "automatically_extensible": True,
                        "utterances": {
                            "boiling": "hot",
                            "cold": "cold",
                            "hot": "hot",
                            "iced": "cold"
                        }
                    }
                },
                "slot_name_mappings": {
                    "MakeCoffee": {
                        "number_of_cups": "snips/number"
                    },
                    "MakeTea": {
                        "beverage_temperature": "Temperature",
                        "number_of_cups": "snips/number"
                    }
                },
            },
            "config": expected_engine_config.to_dict(),
            "intent_parsers": [
                {"unit_name": "test_intent_parser1"},
                {"unit_name": "test_intent_parser2"}
            ],
            "model_version": snips_nlu.version.__model_version__,
            "training_package_version": snips_nlu.__version__
        }

        self.assertDictEqual(actual_engine_dict, expected_engine_dict)

    def test_should_be_deserializable(self):
        # When
        class TestIntentParser1Config(ProcessingUnitConfig):
            unit_name = "test_intent_parser1"

            def to_dict(self):
                return {"unit_name": self.unit_name}

            @classmethod
            def from_dict(cls, obj_dict):
                return TestIntentParser1Config()

        class TestIntentParser1(IntentParser):
            unit_name = "test_intent_parser1"
            config_type = TestIntentParser1Config

            def fit(self, dataset, intents):
                return self

            def get_intent(self, text, intents=None):
                return None

            def get_slots(self, text, intent):
                return []

            def to_dict(self):
                return {
                    "unit_name": self.unit_name,
                }

            @classmethod
            def from_dict(cls, unit_dict):
                config = cls.config_type()
                return TestIntentParser1(config)

        class TestIntentParser2Config(ProcessingUnitConfig):
            unit_name = "test_intent_parser2"

            def to_dict(self):
                return {"unit_name": self.unit_name}

            @classmethod
            def from_dict(cls, obj_dict):
                return TestIntentParser2Config()

        class TestIntentParser2(IntentParser):
            unit_name = "test_intent_parser2"
            config_type = TestIntentParser2Config

            def fit(self, dataset, intents):
                return self

            def get_intent(self, text, intents=None):
                return None

            def get_slots(self, text, intent):
                return []

            def to_dict(self):
                return {
                    "unit_name": self.unit_name,
                }

            @classmethod
            def from_dict(cls, unit_dict):
                config = cls.config_type()
                return TestIntentParser2(config)

        register_processing_unit(TestIntentParser1)
        register_processing_unit(TestIntentParser2)

        dataset_metadata = {
            "language_code": "en",
            "entities": {
                "Temperature": {
                    "automatically_extensible": True,
                    "utterances": {
                        "boiling": "hot",
                        "cold": "cold",
                        "hot": "hot",
                        "iced": "cold"
                    }
                }
            },
            "slot_name_mappings": {
                "MakeCoffee": {
                    "number_of_cups": "snips/number"
                },
                "MakeTea": {
                    "beverage_temperature": "Temperature",
                    "number_of_cups": "snips/number"
                }
            },
        }
        parser1_config = TestIntentParser1Config()
        parser2_config = TestIntentParser2Config()
        engine_config = NLUEngineConfig([parser1_config, parser2_config])
        engine_dict = {
            "unit_name": "nlu_engine",
            "dataset_metadata": dataset_metadata,
            "config": engine_config.to_dict(),
            "intent_parsers": [
                {"unit_name": "test_intent_parser1"},
                {"unit_name": "test_intent_parser2"},
            ],
            "model_version": snips_nlu.version.__model_version__,
            "training_package_version": snips_nlu.__version__
        }
        engine = SnipsNLUEngine.from_dict(engine_dict)

        # Then
        parser1_config = TestIntentParser1Config()
        parser2_config = TestIntentParser2Config()
        expected_engine_config = NLUEngineConfig(
            [parser1_config, parser2_config]).to_dict()
        self.assertDictEqual(engine.dataset_metadata, dataset_metadata)
        self.assertDictEqual(engine.config.to_dict(), expected_engine_config)

    def test_should_parse_after_deserialization(self):
        # Given
        dataset = BEVERAGE_DATASET
        engine = SnipsNLUEngine().fit(dataset)
        input_ = "Give me 3 cups of hot tea please"

        # When
        engine_dict = engine.to_dict()
        deserialized_engine = SnipsNLUEngine.from_dict(engine_dict)
        result = deserialized_engine.parse(input_)

        # Then
        try:
            json.dumps(engine_dict).encode("utf-8")
        except Exception as e:  # pylint: disable=W0703
            trace = tb.format_exc()
            self.fail("SnipsNLUEngine dict should be json serializable "
                      "to utf-8.\n{}\n{}".format(e, trace))
        expected_slots = [
            resolved_slot((8, 9), '3', {'type': 'value', 'value': 3},
                          'snips/number', 'number_of_cups'),
            custom_slot(_slot((18, 21), 'hot', 'Temperature',
                              'beverage_temperature'))
        ]
        self.assertEqual(result[RES_INPUT], input_)
        self.assertEqual(result[RES_INTENT][RES_INTENT_NAME], 'MakeTea')
        self.assertListEqual(result[RES_SLOTS], expected_slots)

    def test_should_fail_when_missing_intents(self):
        # Given
        incomplete_intents = {"MakeCoffee"}
        engine = SnipsNLUEngine()

        # Then
        with self.assertRaises(NotTrained):
            engine.fit(BEVERAGE_DATASET, intents=incomplete_intents)

    def test_should_use_fitted_slot_filler(self):
        # Given
        input_ = "Give me 3 cups of hot tea please"
        fitted_slot_filler = get_fitted_slot_filler(
            SnipsNLUEngine(), BEVERAGE_DATASET, "MakeTea")

        # When
        engine = SnipsNLUEngine()
        add_fitted_slot_filler(engine, "MakeTea", fitted_slot_filler.to_dict())
        engine.fit(BEVERAGE_DATASET, intents=["MakeCoffee"])
        result = engine.parse(input_)

        # Then
        expected_slots = [
            resolved_slot((8, 9), '3', {'type': 'value', 'value': 3},
                          'snips/number', 'number_of_cups'),
            custom_slot(_slot((18, 21), 'hot', 'Temperature',
                              'beverage_temperature'))
        ]
        self.assertEqual(result[RES_INPUT], input_)
        self.assertEqual(result[RES_INTENT][RES_INTENT_NAME], 'MakeTea')
        self.assertListEqual(result[RES_SLOTS], expected_slots)

    def test_should_be_serializable_after_fitted_slot_filler_is_added(self):
        # Given
        input_ = "Give me 3 cups of hot tea please"
        engine = SnipsNLUEngine()
        trained_slot_filler_coffee = get_fitted_slot_filler(
            engine, BEVERAGE_DATASET, "MakeCoffee")
        trained_slot_filler_tea = get_fitted_slot_filler(
            engine, BEVERAGE_DATASET, "MakeTea")

        # When
        engine = SnipsNLUEngine()
        add_fitted_slot_filler(engine, "MakeCoffee",
                               trained_slot_filler_coffee.to_dict())
        add_fitted_slot_filler(engine, "MakeTea",
                               trained_slot_filler_tea.to_dict())
        engine.fit(BEVERAGE_DATASET, intents=[])

        try:
            engine_dict = engine.to_dict()
            new_engine = SnipsNLUEngine.from_dict(engine_dict)
        except Exception as e:  # pylint: disable=W0703
            self.fail('Exception raised: %s\n%s' %
                      (e.message, tb.format_exc()))
        result = new_engine.parse(input_)

        # Then
        expected_slots = [
            resolved_slot((8, 9), '3', {'type': 'value', 'value': 3},
                          'snips/number', 'number_of_cups'),
            custom_slot(_slot((18, 21), 'hot', 'Temperature',
                              'beverage_temperature'))
        ]
        self.assertEqual(result[RES_INPUT], input_)
        self.assertEqual(result[RES_INTENT][RES_INTENT_NAME], 'MakeTea')
        self.assertListEqual(result['slots'], expected_slots)

    @patch(
        "snips_nlu.intent_parser.probabilistic_intent_parser"
        ".ProbabilisticIntentParser.get_slots")
    @patch(
        "snips_nlu.intent_parser.probabilistic_intent_parser"
        ".ProbabilisticIntentParser.get_intent")
    @patch("snips_nlu.intent_parser.deterministic_intent_parser"
           ".DeterministicIntentParser.get_intent")
    def test_should_handle_keyword_entities(self, mocked_regex_get_intent,
                                            mocked_crf_get_intent,
                                            mocked_crf_get_slots):
        # Given
        dataset = {
            "snips_nlu_version": "1.1.1",
            "intents": {
                "dummy_intent_1": {
                    "utterances": [
                        {
                            "data": [
                                {
                                    "text": "dummy_1",
                                    "entity": "dummy_entity_1",
                                    "slot_name": "dummy_slot_name"
                                },
                                {
                                    "text": " dummy_2",
                                    "entity": "dummy_entity_2",
                                    "slot_name": "other_dummy_slot_name"
                                }
                            ]
                        }
                    ]
                }
            },
            "entities": {
                "dummy_entity_1": {
                    "use_synonyms": True,
                    "automatically_extensible": False,
                    "data": [
                        {
                            "value": "dummy1",
                            "synonyms": [
                                "dummy1",
                                "dummy1_bis"
                            ]
                        },
                        {
                            "value": "dummy2",
                            "synonyms": [
                                "dummy2",
                                "dummy2_bis"
                            ]
                        }
                    ]
                },
                "dummy_entity_2": {
                    "use_synonyms": False,
                    "automatically_extensible": True,
                    "data": [
                        {
                            "value": "dummy2",
                            "synonyms": [
                                "dummy2"
                            ]
                        }
                    ]
                }
            },
            "language": "en"
        }

        mocked_crf_intent = intent_classification_result("dummy_intent_1", 1.0)
        mocked_crf_slots = [_slot(match_range=(0, 7),
                                  value="dummy_3",
                                  entity="dummy_entity_1",
                                  slot_name="dummy_slot_name"),
                            _slot(match_range=(8, 15),
                                  value="dummy_4",
                                  entity="dummy_entity_2",
                                  slot_name="other_dummy_slot_name")]

        mocked_regex_get_intent.return_value = None
        mocked_crf_get_intent.return_value = mocked_crf_intent
        mocked_crf_get_slots.return_value = mocked_crf_slots

        engine = SnipsNLUEngine()
        text = "dummy_3 dummy_4"

        # When
        engine = engine.fit(dataset)
        result = engine.parse(text)

        # Then
        expected_slot = custom_slot(_slot(
            match_range=(8, 15), value="dummy_4", entity="dummy_entity_2",
            slot_name="other_dummy_slot_name"))
        expected_result = parsing_result(text, intent=mocked_crf_intent,
                                         slots=[expected_slot])
        self.assertEqual(expected_result, result)

    @patch(
        "snips_nlu.intent_parser.probabilistic_intent_parser"
        ".ProbabilisticIntentParser.get_slots")
    @patch(
        "snips_nlu.intent_parser.probabilistic_intent_parser"
        ".ProbabilisticIntentParser.get_intent")
    @patch("snips_nlu.intent_parser.deterministic_intent_parser"
           ".DeterministicIntentParser.get_intent")
    def test_synonyms_should_point_to_base_value(self, mocked_deter_get_intent,
                                                 mocked_proba_get_intent,
                                                 mocked_proba_get_slots):
        # Given
        dataset = {
            "snips_nlu_version": "1.1.1",
            "intents": {
                "dummy_intent_1": {
                    "utterances": [
                        {
                            "data": [
                                {
                                    "text": "dummy_1",
                                    "entity": "dummy_entity_1",
                                    "slot_name": "dummy_slot_name"
                                }
                            ]
                        }
                    ]
                }
            },
            "entities": {
                "dummy_entity_1": {
                    "use_synonyms": True,
                    "automatically_extensible": False,
                    "data": [
                        {
                            "value": "dummy1",
                            "synonyms": [
                                "dummy1",
                                "dummy1_bis"
                            ]
                        }
                    ]
                }
            },
            "language": "en"
        }

        mocked_proba_parser_intent = intent_classification_result(
            "dummy_intent_1", 1.0)
        mocked_proba_parser_slots = [
            _slot(match_range=(0, 10), value="dummy1_bis",
                  entity="dummy_entity_1",
                  slot_name="dummy_slot_name")]

        mocked_deter_get_intent.return_value = None
        mocked_proba_get_intent.return_value = mocked_proba_parser_intent
        mocked_proba_get_slots.return_value = mocked_proba_parser_slots

        engine = SnipsNLUEngine().fit(dataset)
        text = "dummy1_bis"

        # When
        result = engine.parse(text)

        # Then
        expected_slot = {
            RES_MATCH_RANGE: [0, 10],
            RES_RAW_VALUE: "dummy1_bis",
            RES_VALUE: {
                "kind": "Custom",
                "value": "dummy1"
            },
            RES_ENTITY: "dummy_entity_1",
            RES_SLOT_NAME: "dummy_slot_name"
        }
        expected_result = parsing_result(
            text, intent=mocked_proba_parser_intent, slots=[expected_slot])
        self.assertEqual(expected_result, result)

    def test_enrich_slots(self):
        # Given
        slots = [
            # Adjacent
            {
                "slots": [
                    _slot((0, 2), "", "", ""),
                    _slot((6, 8), "", "", "")
                ],
                "other_slots": [
                    _slot((2, 6), "", "", ""),
                    _slot((8, 10), "", "", "")
                ],
                "enriched": [
                    _slot((0, 2), "", "", ""),
                    _slot((6, 8), "", "", ""),
                    _slot((2, 6), "", "", ""),
                    _slot((8, 10), "", "", "")
                ]
            },
            # Equality
            {
                "slots": [
                    _slot((0, 2), "", "", ""),
                    _slot((6, 8), "", "", "")
                ],
                "other_slots": [
                    _slot((6, 8), "", "", ""),
                ],
                "enriched": [
                    _slot((0, 2), "", "", ""),
                    _slot((6, 8), "", "", "")
                ]
            },
            # Inclusion
            {
                "slots": [
                    _slot((0, 2), "", "", ""),
                    _slot((6, 8), "", "", "")
                ],
                "other_slots": [
                    _slot((5, 7), "", "", ""),
                ],
                "enriched": [
                    _slot((0, 2), "", "", ""),
                    _slot((6, 8), "", "", "")
                ]
            },
            # Cross upper
            {
                "slots": [
                    _slot((0, 2), "", "", ""),
                    _slot((6, 8), "", "", "")
                ],
                "other_slots": [
                    _slot((7, 10), "", "", ""),
                ],
                "enriched": [
                    _slot((0, 2), "", "", ""),
                    _slot((6, 8), "", "", "")
                ]
            },
            # Cross lower
            {
                "slots": [
                    _slot((0, 2), "", "", ""),
                    _slot((6, 8), "", "", "")
                ],
                "other_slots": [
                    _slot((5, 7), "", "", ""),
                ],
                "enriched": [
                    _slot((0, 2), "", "", ""),
                    _slot((6, 8), "", "", "")
                ]
            },
            # Full overlap
            {
                "slots": [
                    _slot((0, 2), "", "", ""),
                    _slot((6, 8), "", "", "")
                ],
                "other_slots": [
                    _slot((4, 12), "", "", ""),
                ],
                "enriched": [
                    _slot((0, 2), "", "", ""),
                    _slot((6, 8), "", "", "")
                ]
            }
        ]

        for data in slots:
            # When
            enriched = enrich_slots(data["slots"], data["other_slots"])

            # Then
            self.assertEqual(enriched, data["enriched"])

    def test_should_parse_naughty_strings(self):
        # Given
        dataset = SAMPLE_DATASET
        naughty_strings_path = os.path.join(TEST_PATH, "resources",
                                            "naughty_strings.txt")
        with io.open(naughty_strings_path, encoding='utf8') as f:
            naughty_strings = [line.strip("\n") for line in f.readlines()]

        # When
        engine = SnipsNLUEngine().fit(dataset)

        # Then
        for s in naughty_strings:
            try:
                engine.parse(s)
            except:  # pylint: disable=W0702
                trace = tb.format_exc()
                self.fail('Exception raised:\n %s' % trace)

    def test_should_fit_with_naughty_strings(self):
        # Given
        naughty_strings_path = os.path.join(TEST_PATH, "resources",
                                            "naughty_strings.txt")
        with io.open(naughty_strings_path, encoding='utf8') as f:
            naughty_strings = [line.strip("\n") for line in f.readlines()]
        utterances = [{DATA: [{TEXT: naughty_string}]} for naughty_string in
                      naughty_strings]

        # When
        naughty_dataset = validate_and_format_dataset({
            "intents": {
                "naughty_intent": {
                    "utterances": utterances
                }
            },
            "entities": dict(),
            "language": "en",
            "snips_nlu_version": "0.0.1"
        })

        # Then
        try:
            SnipsNLUEngine().fit(naughty_dataset)
        except:  # pylint: disable=W0702
            trace = tb.format_exc()
            self.fail('Exception raised:\n %s' % trace)

    def test_engine_should_fit_with_builtins_entities(self):
        # Given
        dataset = validate_and_format_dataset({
            "intents": {
                "dummy": {
                    "utterances": [
                        {
                            "data": [
                                {
                                    "text": "10p.m.",
                                    "entity": "snips/datetime",
                                    "slot_name": "startTime"
                                }
                            ]
                        }
                    ]
                }
            },
            "entities": {
                "snips/datetime": {}
            },
            "language": "en",
            "snips_nlu_version": "0.0.1"
        })

        # When / Then
        try:
            SnipsNLUEngine().fit(dataset)
        except:  # pylint: disable=W0702
            self.fail("NLU engine should fit builtin")

    def test_get_fitted_slot_filler_should_return_same_slot_filler_as_fit(
            self):
        # Given
        intent = "MakeCoffee"
        slot_filler_config = CRFSlotFillerConfig(random_seed=42)
        parser_config = ProbabilisticIntentParserConfig(
            slot_filler_config=slot_filler_config)
        config = NLUEngineConfig(intent_parsers_configs=[parser_config])
        trained_engine = SnipsNLUEngine(config).fit(BEVERAGE_DATASET)

        # When
        engine = SnipsNLUEngine(config)
        slot_filler = get_fitted_slot_filler(engine, BEVERAGE_DATASET, intent)

        # Then
        expected_slot_filler = \
            trained_engine.intent_parsers[0].slot_fillers[intent]
        self.assertEqual(expected_slot_filler.crf_model.state_features_,
                         slot_filler.crf_model.state_features_)
        self.assertEqual(expected_slot_filler.crf_model.transition_features_,
                         slot_filler.crf_model.transition_features_)

    @patch("snips_nlu.intent_parser.probabilistic_intent_parser."
           "ProbabilisticIntentParser.get_slots")
    @patch("snips_nlu.intent_parser.probabilistic_intent_parser."
           "ProbabilisticIntentParser.get_intent")
    def test_parse_should_call_probabilistic_intent_parser_when_given_intent(
            self, mocked_probabilistic_get_intent,
            mocked_probabilistic_get_slots):
        # Given
        dataset = deepcopy(SAMPLE_DATASET)
        dataset["entities"]["dummy_entity_1"][
            "automatically_extensible"] = True
        engine = SnipsNLUEngine().fit(dataset)
        intent = "dummy_intent_1"
        text = "This is another weird weird query"

        intent_classif_result = intent_classification_result(intent, .8)
        expected_intent_classif_result = intent_classification_result(intent,
                                                                      1.0)
        mocked_probabilistic_get_intent.return_value = intent_classif_result

        parsed_slots = [
            _slot(match_range=(16, 27), value="weird weird",
                  entity="dummy_entity_1",
                  slot_name="dummy slot nàme")]
        mocked_probabilistic_get_slots.return_value = parsed_slots

        # When
        parse = engine.parse(text, intent=intent)

        # Then
        mocked_probabilistic_get_intent.assert_called_once()
        mocked_probabilistic_get_slots.assert_called_once()
        resolved_slots = [custom_slot(s) for s in parsed_slots]
        expected_parse = parsing_result(text, expected_intent_classif_result,
                                        resolved_slots)
        self.assertEqual(expected_parse, parse)

    def test_nlu_engine_should_train_and_parse_in_all_languages(self):
        # Given
        text = "brew me an expresso"
        for l in Language:
            dataset = deepcopy(BEVERAGE_DATASET)
            dataset[LANGUAGE] = l.iso_code
            engine = SnipsNLUEngine()

            # When / Then
            try:
                engine = engine.fit(dataset)
            except:  # pylint: disable=W0702
                self.fail("Could not fit engine in '%s': %s"
                          % (l.iso_code, tb.format_exc()))

            try:
                engine.parse(text)
            except:  # pylint: disable=W0702
                self.fail("Could not fit engine in '%s': %s"
                          % (l.iso_code, tb.format_exc()))
