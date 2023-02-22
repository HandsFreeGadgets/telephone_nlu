# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions
import abc
import os
import pty
import re
from copy import copy
from pathlib import Path
from typing import Any, Text, Dict, List

import phonetics
from rasa_sdk import Action, Tracker
from rasa_sdk.events import AllSlotsReset, FollowupAction
from rasa_sdk.executor import CollectingDispatcher
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.future import Engine, select
from sqlalchemy.orm import declarative_base, Session

DB_FILENAME = 'telephone.db'
CONFIG_PATH = str(Path.home()) + "/telephone_nlu"
Base = declarative_base()


class SIPClient:

    @staticmethod
    def _clean_number_(number: str):
        number = number.replace('plus', '+')
        number = re.sub(r'\s*', '', number)
        return number

    @abc.abstractmethod
    def call_number(self, number: str):
        pass

    @abc.abstractmethod
    def hangup(self):
        pass

    @abc.abstractmethod
    def hold(self):
        pass

    @abc.abstractmethod
    def mute(self):
        pass

    @abc.abstractmethod
    def accept(self):
        pass

    @abc.abstractmethod
    def reject(self):
        pass


class SIPSimple(SIPClient):

    def __send_command__(self, command: str):
        pty.spawn(['screen', '-T', 'vt100', '-p', '0', '-S', 'sip-session', '-X', 'stuff', '{}^M'.format(command)])

    def call_number(self, number: str):
        self.__send_command__('/audio {}'.format(SIPClient._clean_number_(number)))

    def hangup(self):
        self.__send_command__('/hangup')

    def hold(self):
        self.__send_command__('/hold')

    def mute(self):
        self.__send_command__('/mute')

    def accept(self):
        self.__send_command__('/a')

    def reject(self):
        self.__send_command__('/r')


class Baresip(SIPClient):

    def __send_command__(self, command: str):
        pty.spawn(['screen', '-T', 'vt100', '-p', '0', '-S', 'baresip', '-X', 'stuff', '{}^M'.format(command)])

    def call_number(self, number: str):
        self.__send_command__('/dial {}'.format(SIPClient._clean_number_(number)))

    def hangup(self):
        self.__send_command__('/hangup')

    def hold(self):
        # not supported
        pass

    def mute(self):
        self.__send_command__('m')

    def accept(self):
        self.__send_command__('/accept')

    def reject(self):
        self.__send_command__('/hangup')


sipclient = Baresip()


def __get_db_engine__() -> Engine:
    os.makedirs(CONFIG_PATH, exist_ok=True)
    engine = create_engine("sqlite+pysqlite:///" + CONFIG_PATH + "/" + DB_FILENAME, echo=True, future=True)
    Base.metadata.create_all(engine)
    return engine


class Contact(Base):
    __tablename__ = 'contact'
    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, unique=True)
    fuzzy_name = Column(String(32), nullable=False, unique=True)
    number = Column(String(16), nullable=False)

    def __repr__(self):
        return f"Contact(id={self.id!r}, name={self.name!r}, number={self.number!r})"


def __text_number_to_number__(number: str) -> str:
    replacements = {'null': '0', 'plus': '+',
                    'eins': '1', 'zwei': '2',
                    'drei': '3', 'vier': '4',
                    'fünf': '5', 'sechs': '6',
                    'sieben': '7', 'acht': '8',
                    'zwo': '2', 'neun': '9'}
    for i, j in replacements.items():
        number = number.replace(i, j)
    number = number.strip(".")
    return number


def __delete_contact__(name: str):
    engine = __get_db_engine__()
    with Session(engine) as session:
        existing_contact = session.execute(select(Contact).filter_by(fuzzy_name=phonetics.dmetaphone(name)[0])).scalar_one_or_none()
        if existing_contact:
            session.delete(existing_contact)
            session.commit()


def __insert_contact__(name: str, number: str):
    engine = __get_db_engine__()
    # if at end of sentence
    number = __text_number_to_number__(number)
    with Session(engine) as session:
        existing_contact = session.execute(select(Contact).filter_by(fuzzy_name=phonetics.dmetaphone(name)[0])).scalar_one_or_none()
        if existing_contact:
            existing_contact.number = number
        else:
            contact = Contact(name=name, number=number, fuzzy_name=phonetics.dmetaphone(name)[0])
            session.add(contact)
        session.commit()


def __get_contact__(name: str) -> Contact:
    engine = __get_db_engine__()
    with Session(engine) as session:
        contact = session.execute(
            select(Contact).filter_by(fuzzy_name=phonetics.dmetaphone(name)[0])).scalar_one_or_none()
        contact = copy(contact)
        session.commit()
    return contact


class ActionCallReject(Action):
    def name(self) -> Text:
        return "action_call_reject"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        sipclient.reject()

        return [AllSlotsReset(), FollowupAction('action_listen')]


class ActionCallTerminate(Action):
    def name(self) -> Text:
        return "action_call_terminate"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        sipclient.hangup()

        return [AllSlotsReset(), FollowupAction('action_listen')]


class ActionCallAccept(Action):
    def name(self) -> Text:
        return "action_call_accept"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        sipclient.accept()

        return [AllSlotsReset(), FollowupAction('action_listen')]


class ActionCallMute(Action):
    def name(self) -> Text:
        return "action_call_mute"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        sipclient.mute()

        return [AllSlotsReset(), FollowupAction('action_listen')]


class ActionHold(Action):
    def name(self) -> Text:
        return "action_call_hold"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        sipclient.hold()

        return [AllSlotsReset(), FollowupAction('action_listen')]


class ActionCallContact(Action):
    def name(self) -> Text:
        return "action_call_contact"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        person_name = tracker.get_slot("PERSON")
        if not person_name:
            dispatcher.utter_message(text="utter_contact_not_given")
        else:
            person_name = ' '.join(person_name)
            try:
                contact = __get_contact__(person_name)
            except Exception as e:
                dispatcher.utter_message(template="utter_telephone_database_error")
                raise e
            if not contact:
                dispatcher.utter_message(template="utter_telephone_person_not_found", person=person_name)
            else:
                dispatcher.utter_message(template="utter_dial_contact", PERSON=person_name)
                sipclient.call_number(contact.number)

        return [AllSlotsReset(), FollowupAction('action_listen')]


class ActionCallNumber(Action):
    def name(self) -> Text:
        return "action_call_number"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        number = tracker.get_slot("phone_number")
        if not number:
            dispatcher.utter_message(text="utter_number_not_given")
        else:
            dispatcher.utter_message(template="utter_dial_number", phone_number=number)
            sipclient.call_number(__text_number_to_number__(number))

        return [AllSlotsReset(), FollowupAction('action_listen')]


class ActionSaveContact(Action):
    def name(self) -> Text:
        return "action_save_contact"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        number = tracker.get_slot("phone_number")
        if not number:
            dispatcher.utter_message(text="utter_number_missing")
        else:
            person_name = tracker.get_slot("PERSON")
            if not person_name:
                dispatcher.utter_message(text="utter_person_missing")
            else:
                person_name = ' '.join(person_name)
                try:
                    __insert_contact__(person_name, __text_number_to_number__(number))
                    dispatcher.utter_message(template="utter_saved_contact", name=person_name, number=number)
                except Exception as e:
                    dispatcher.utter_message(text="utter_telephone_database_error")
                    raise e

        return [AllSlotsReset(), FollowupAction('action_listen')]


class ActionDeleteContact(Action):
    def name(self) -> Text:
        return "action_delete_contact"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        person_name = tracker.get_slot("PERSON")
        if not person_name:
            dispatcher.utter_message(text="utter_person_missing")
        else:
            person_name = ' '.join(person_name)
            try:
                contact = __get_contact__(person_name)
            except Exception as e:
                dispatcher.utter_message(template="utter_telephone_database_error")
                raise e
            if not contact:
                dispatcher.utter_message(template="utter_telephone_person_not_found", person=person_name)
            else:
                try:
                    __delete_contact__(person_name)
                    dispatcher.utter_message(template="utter_deleted_contact", name=person_name)
                except Exception as e:
                    dispatcher.utter_message(text="utter_telephone_database_error")
                    raise e

        return [AllSlotsReset(), FollowupAction('action_listen')]