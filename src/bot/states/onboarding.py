"""FSM States for Candidate Onboarding."""

from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    waiting_for_cv = State()
    wizard_title = State()
    wizard_education = State()
    wizard_experience = State()
    wizard_skills = State()
    wizard_preferences = State()

