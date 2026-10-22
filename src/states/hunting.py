from src.states.base_state import State

class HuntingState(State):
    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def check_transitions(self):
        return None

    def on_frame(self):
        # Hit-react FIRST: retreat/jump, skip route and combat overwrite
        if getattr(self.bot, "handle_hit_react_frame", lambda: False)():
            return

        # Stuck / off-route / minimap-lost recovery: pause attacks, prefer route,
        # soft random only after delay, halt if recovery fails too long.
        if getattr(self.bot, "handle_recovery_frame", lambda: False)():
            self.bot.kb.set_command(self.bot.cmd_move_x + ' ' +
                                    self.bot.cmd_move_y + ' ' +
                                    self.bot.cmd_action)
            if self.bot.cmd_action in ("jump", "teleport", "attack", "aoe_attack"):
                self.bot.cmd_action = "none"
            return

        engaging = getattr(self.bot, "is_engaging", lambda: False)()
        soft_target = getattr(self.bot, "has_soft_combat_target", lambda: False)()

        # Skip route overwrite while finish-kill engage-hold or soft TTL target
        if not (engaging or soft_target):
            # Get commend from route map
            self.bot.update_cmd_by_route()

            # Check if reach goal on route map
            self.bot.check_reach_goal()

        # Get attack commend by detecting mobs near players
        self.bot.update_cmd_by_mob_detection()

        # Soft target can appear after detection; re-check for stuck recovery
        soft_target = getattr(self.bot, "has_soft_combat_target", lambda: False)()
        engaging = getattr(self.bot, "is_engaging", lambda: False)()

        # Legacy fallback ONLY when recovery is disabled.
        # When recovery.enable, handle_recovery_frame fully owns stuck handling
        # (no jump=True update_cmd_by_random from this path).
        recovery_on = True
        try:
            recovery_on = bool(self.bot._recovery_enabled())
        except Exception:
            recovery_on = True
        if (not recovery_on
                and not self.bot.monsters
                and not soft_target
                and not engaging
                and self.bot.is_player_stuck()):
            self.bot.update_cmd_by_random(allow_jump=False)

        # send command to keyboard controller
        self.bot.kb.set_command(self.bot.cmd_move_x + ' ' + \
                                self.bot.cmd_move_y + ' ' + \
                                self.bot.cmd_action)
        # One-shot actions must not stick on the bot either. Otherwise later
        # frames keep set_command(... aoe_attack/attack/jump/teleport) and the
        # keyboard thread presses again every frame even after clearing locally.
        if self.bot.cmd_action in ("jump", "teleport", "attack", "aoe_attack"):
            self.bot.cmd_action = "none"
