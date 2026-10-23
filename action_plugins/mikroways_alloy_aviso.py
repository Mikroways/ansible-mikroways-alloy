# -*- coding: utf-8 -*-
# Aviso del rol mikroways.alloy. ansible-core no trae un módulo "warn": esta
# action plugin emite el aviso como warning de Ansible, lo suma a las custom
# stats (se ven después del PLAY RECAP con ANSIBLE_SHOW_CUSTOM_STATS=true) y
# lo acumula en ansible_facts.alloy_avisos, que usan las pruebas.
#
#   mikroways_alloy_aviso: {msg: "..."}        emite un aviso
#   mikroways_alloy_aviso: {msg: ["...", ...]} emite varios (vacía: nada)
#   mikroways_alloy_aviso: {reset: true}       vacía ansible_facts.alloy_avisos
#
# No usarla en un loop: los facts de cada ítem no se ven en el siguiente y el
# acumulado queda solo con el último. Para varios avisos, pasar una lista.
from __future__ import annotations

from ansible.errors import AnsibleActionFail
from ansible.module_utils.parsing.convert_bool import boolean
from ansible.plugins.action import ActionBase

FACT = "alloy_avisos"


class ActionModule(ActionBase):
    TRANSFERS_FILES = False
    _requires_connection = False
    _VALID_ARGS = frozenset(("msg", "reset"))

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        task_vars = task_vars or {}
        result["changed"] = False

        if boolean(self._task.args.get("reset", False), strict=False):
            result["ansible_facts"] = {FACT: []}
            return result

        if "msg" not in self._task.args:
            raise AnsibleActionFail("mikroways_alloy_aviso necesita msg o reset")
        raw = self._task.args["msg"]
        if isinstance(raw, (list, tuple)):
            msgs = [" ".join(str(m).split()) for m in raw]
        else:
            msgs = [" ".join(str(raw).split())]
        msgs = [m for m in msgs if m]
        if not msgs:
            return result

        host = task_vars.get("inventory_hostname", "")
        previos = list((task_vars.get("ansible_facts") or {}).get(FACT) or [])

        result.update(
            msg=msgs,
            warnings=[f"mikroways.alloy en {host}: {m}" for m in msgs],
            ansible_facts={FACT: previos + msgs},
            ansible_stats={
                "data": {FACT: msgs},
                "per_host": True,
                "aggregate": True,
            },
        )
        return result
