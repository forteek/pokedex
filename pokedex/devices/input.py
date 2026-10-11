from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol

import pygame


class Action(Enum):
    LEFT = auto()
    RIGHT = auto()
    UP = auto()
    DOWN = auto()
    CONFIRM = auto()
    HOME = auto()
    SCAN = auto()


@dataclass(frozen=True)
class InputFrame:
    """Actions pressed during one app frame, plus a request to quit."""

    actions: frozenset[Action] = frozenset()
    quit_requested: bool = False


class InputDevice(Protocol):
    def poll(self) -> InputFrame: ...


class PygameInput:
    """Translate pygame events into platform-independent app actions."""

    KEY_ACTIONS = {
        pygame.K_LEFT: Action.LEFT,
        pygame.K_RIGHT: Action.RIGHT,
        pygame.K_UP: Action.UP,
        pygame.K_DOWN: Action.DOWN,
        pygame.K_q: Action.CONFIRM,
        pygame.K_w: Action.HOME,
        pygame.K_e: Action.SCAN,
    }

    def poll(self) -> InputFrame:
        actions: set[Action] = set()
        quit_requested = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_requested = True
            elif event.type == pygame.KEYDOWN:
                action = self.KEY_ACTIONS.get(event.key)
                if action is not None:
                    actions.add(action)

        return InputFrame(frozenset(actions), quit_requested)
