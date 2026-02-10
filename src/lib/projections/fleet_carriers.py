from datetime import datetime, timedelta, timezone
from typing import Any

from typing_extensions import override
from pydantic import BaseModel, Field

from ..Event import Event, GameEvent, ProjectedEvent
from ..EventManager import Projection


class FleetCarrierEntry(BaseModel):
    """Fleet carrier details and last known location."""
    CarrierType: str = Field(default="Unknown", description="Carrier type (FleetCarrier/SquadronCarrier)")
    CarrierID: int = Field(default=0, description="Carrier identifier")
    Callsign: str = Field(default="Unknown", description="Carrier callsign")
    Name: str = Field(default="Unknown", description="Carrier name")
    DockingAccess: str = Field(default="Unknown", description="Docking access mode")
    AllowNotorious: bool = Field(default=False, description="Whether notorious pilots are allowed")
    FuelLevel: int = Field(default=0, description="Carrier fuel level")
    JumpRangeCurr: float = Field(default=0.0, description="Current jump range")
    JumpRangeMax: float = Field(default=0.0, description="Maximum jump range")
    PendingDecommission: bool = Field(default=False, description="Whether decommission is pending")
    SpaceUsage: dict[str, Any] = Field(default_factory=dict, description="Carrier space usage data")
    Finance: dict[str, Any] = Field(default_factory=dict, description="Carrier finance data")
    Crew: list[dict[str, Any]] = Field(default_factory=list, description="Carrier crew data")
    ShipPacks: list[dict[str, Any]] = Field(default_factory=list, description="Carrier ship packs")
    ModulePacks: list[dict[str, Any]] = Field(default_factory=list, description="Carrier module packs")
    TradeOrders: dict[str, dict[str, Any]] = Field(default_factory=dict, description="Carrier trade orders keyed by commodity")
    StarSystem: str = Field(default="Unknown", description="Last known star system")
    SystemAddress: int = Field(default=0, description="Last known system address")
    BodyID: int = Field(default=0, description="Last known body ID")
    Timestamp: str = Field(default="1970-01-01T00:00:00Z", description="Timestamp of last carrier update")


class CarrierJumpRequestItem(BaseModel):
    """Pending carrier jump request."""
    CarrierType: str = Field(default="Unknown", description="Carrier type (FleetCarrier/SquadronCarrier)")
    CarrierID: int = Field(default=0, description="Carrier identifier")
    SystemName: str = Field(default="Unknown", description="Destination system name")
    Body: str = Field(default="Unknown", description="Destination body name")
    SystemAddress: int = Field(default=0, description="Destination system address")
    BodyID: int = Field(default=0, description="Destination body ID")
    DepartureTime: str = Field(default="1970-01-01T00:00:00Z", description="Scheduled departure time (UTC)")
    WarningSent: bool = Field(default=False, description="Whether a jump warning has been sent")


class CarrierCooldownItem(BaseModel):
    """Carrier jump cooldown tracking."""
    CarrierType: str = Field(default="Unknown", description="Carrier type (FleetCarrier/SquadronCarrier)")
    CarrierID: int = Field(default=0, description="Carrier identifier")
    CooldownUntil: str = Field(default="1970-01-01T00:00:00Z", description="Carrier jump cooldown end time (UTC)")
    ReadySent: bool = Field(default=False, description="Whether cooldown ready event has been sent")


class FleetCarriersStateModel(BaseModel):
    """Fleet carriers keyed by carrier ID."""
    Carriers: dict[int, FleetCarrierEntry] = Field(default_factory=dict, description="Carriers keyed by CarrierID")
    PendingJumps: dict[int, CarrierJumpRequestItem] = Field(default_factory=dict, description="Pending carrier jumps keyed by CarrierID")
    Cooldowns: dict[int, CarrierCooldownItem] = Field(default_factory=dict, description="Carrier cooldowns keyed by CarrierID")


class FleetCarriers(Projection[FleetCarriersStateModel]):
    StateModel = FleetCarriersStateModel

    def _ensure_entry(self, carrier_id: int, carrier_type: str) -> FleetCarrierEntry:
        entry = self.state.Carriers.get(carrier_id)
        if entry is None:
            entry = FleetCarrierEntry(CarrierID=carrier_id, CarrierType=carrier_type)
            self.state.Carriers[carrier_id] = entry
        return entry

    def _process_jump_timers(self, current_time: datetime) -> list[ProjectedEvent]:
        projected_events: list[ProjectedEvent] = []
        completed_ids: list[int] = []
        cooldown_completed_ids: list[int] = []

        for carrier_id, pending in self.state.PendingJumps.items():
            try:
                departure_time = datetime.fromisoformat(pending.DepartureTime.replace("Z", "+00:00"))
            except ValueError:
                continue

            warning_time = departure_time - timedelta(minutes=10)
            if current_time >= warning_time and not pending.WarningSent:
                projected_events.append(ProjectedEvent(content={
                    "event": "CarrierJumpWarning",
                    "CarrierType": pending.CarrierType,
                    "CarrierID": carrier_id,
                    "SystemName": pending.SystemName,
                    "Body": pending.Body,
                    "SystemAddress": pending.SystemAddress,
                    "BodyID": pending.BodyID,
                    "DepartureTime": pending.DepartureTime,
                }))
                pending.WarningSent = True

            if current_time >= departure_time:
                entry = self.state.Carriers.get(carrier_id)
                if entry is None:
                    entry = FleetCarrierEntry(CarrierID=carrier_id, CarrierType=pending.CarrierType)
                    self.state.Carriers[carrier_id] = entry

                entry.CarrierType = pending.CarrierType
                entry.StarSystem = pending.SystemName
                entry.SystemAddress = pending.SystemAddress
                entry.BodyID = pending.BodyID
                entry.Timestamp = pending.DepartureTime
                cooldown_until = departure_time + timedelta(minutes=15)
                self.state.Cooldowns[carrier_id] = CarrierCooldownItem(
                    CarrierType=pending.CarrierType,
                    CarrierID=carrier_id,
                    CooldownUntil=cooldown_until.isoformat(),
                    ReadySent=False,
                )

                projected_events.append(ProjectedEvent(content={
                    "event": "CarrierJumpArrived",
                    "CarrierType": pending.CarrierType,
                    "CarrierID": carrier_id,
                    "SystemName": pending.SystemName,
                    "Body": pending.Body,
                    "SystemAddress": pending.SystemAddress,
                    "BodyID": pending.BodyID,
                    "DepartureTime": pending.DepartureTime,
                }))
                completed_ids.append(carrier_id)

        for carrier_id in completed_ids:
            self.state.PendingJumps.pop(carrier_id, None)

        for carrier_id, cooldown in self.state.Cooldowns.items():
            if cooldown.ReadySent:
                continue
            try:
                cooldown_until = datetime.fromisoformat(cooldown.CooldownUntil.replace("Z", "+00:00"))
            except ValueError:
                continue
            if current_time >= cooldown_until:
                projected_events.append(ProjectedEvent(content={
                    "event": "CarrierJumpCooldownComplete",
                    "CarrierType": cooldown.CarrierType,
                    "CarrierID": carrier_id,
                    "CooldownUntil": cooldown.CooldownUntil,
                }))
                cooldown.ReadySent = True
                cooldown_completed_ids.append(carrier_id)

        for carrier_id in cooldown_completed_ids:
            self.state.Cooldowns.pop(carrier_id, None)

        return projected_events

    @override
    def process(self, event: Event) -> list[ProjectedEvent] | None:
        if not isinstance(event, GameEvent):
            return None

        event_name = event.content.get("event")
        if event_name not in [
            "CarrierLocation",
            "CarrierStats",
            "CarrierJumpRequest",
            "CarrierJumpCancelled",
            "CarrierNameChanged",
            "CarrierDecommission",
            "CarrierCancelDecommission",
            "CarrierBankTransfer",
            "CarrierDepositFuel",
            "CarrierCrewServices",
            "CarrierFinance",
            "CarrierTradeOrder",
        ]:
            return None

        carrier_id_value = event.content.get("CarrierID", 0)
        if not isinstance(carrier_id_value, int) or not carrier_id_value:
            return None
        carrier_id = carrier_id_value

        carrier_type = event.content.get("CarrierType", "Unknown")
        if not isinstance(carrier_type, str):
            carrier_type = "Unknown"
        entry = self._ensure_entry(carrier_id, carrier_type)

        entry.CarrierType = carrier_type
        entry.CarrierID = carrier_id
        timestamp = event.content.get("timestamp")
        if isinstance(timestamp, str):
            entry.Timestamp = timestamp

        if event_name == "CarrierLocation":
            star_system = event.content.get("StarSystem")
            system_address = event.content.get("SystemAddress")
            body_id = event.content.get("BodyID")
            star_system = star_system if isinstance(star_system, str) else entry.StarSystem
            system_address = system_address if isinstance(system_address, int) else entry.SystemAddress
            body_id = body_id if isinstance(body_id, int) else entry.BodyID
            entry.StarSystem = star_system
            entry.SystemAddress = system_address
            entry.BodyID = body_id

        if event_name == "CarrierStats":
            callsign = event.content.get("Callsign")
            name = event.content.get("Name")
            docking_access = event.content.get("DockingAccess")
            allow_notorious = event.content.get("AllowNotorious")
            fuel_level = event.content.get("FuelLevel")
            jump_range_curr = event.content.get("JumpRangeCurr")
            jump_range_max = event.content.get("JumpRangeMax")
            pending_decommission = event.content.get("PendingDecommission")
            space_usage = event.content.get("SpaceUsage")
            finance = event.content.get("Finance")
            crew = event.content.get("Crew")
            ship_packs = event.content.get("ShipPacks")
            module_packs = event.content.get("ModulePacks")
            callsign = callsign if isinstance(callsign, str) else entry.Callsign
            name = name if isinstance(name, str) else entry.Name
            docking_access = docking_access if isinstance(docking_access, str) else entry.DockingAccess
            allow_notorious = allow_notorious if isinstance(allow_notorious, bool) else entry.AllowNotorious
            fuel_level = fuel_level if isinstance(fuel_level, int) else entry.FuelLevel
            jump_range_curr = jump_range_curr if isinstance(jump_range_curr, (int, float)) else entry.JumpRangeCurr
            jump_range_max = jump_range_max if isinstance(jump_range_max, (int, float)) else entry.JumpRangeMax
            pending_decommission = pending_decommission if isinstance(pending_decommission, bool) else entry.PendingDecommission
            space_usage = space_usage if isinstance(space_usage, dict) else entry.SpaceUsage
            finance = finance if isinstance(finance, dict) else entry.Finance
            crew = crew if isinstance(crew, list) else entry.Crew
            ship_packs = ship_packs if isinstance(ship_packs, list) else entry.ShipPacks
            module_packs = module_packs if isinstance(module_packs, list) else entry.ModulePacks
            entry.Callsign = callsign
            entry.Name = name
            entry.DockingAccess = docking_access
            entry.AllowNotorious = allow_notorious
            entry.FuelLevel = fuel_level
            entry.JumpRangeCurr = float(jump_range_curr)
            entry.JumpRangeMax = float(jump_range_max)
            entry.PendingDecommission = pending_decommission
            entry.SpaceUsage = space_usage
            entry.Finance = finance
            entry.Crew = crew
            entry.ShipPacks = ship_packs
            entry.ModulePacks = module_packs

        if event_name == "CarrierNameChanged":
            callsign = event.content.get("Callsign")
            name = event.content.get("Name")
            callsign = callsign if isinstance(callsign, str) else entry.Callsign
            name = name if isinstance(name, str) else entry.Name
            entry.Callsign = callsign
            entry.Name = name

        if event_name == "CarrierDecommission":
            entry.PendingDecommission = True

        if event_name == "CarrierCancelDecommission":
            entry.PendingDecommission = False

        if event_name == "CarrierBankTransfer":
            carrier_balance = event.content.get("CarrierBalance")
            player_balance = event.content.get("PlayerBalance")
            deposit = event.content.get("Deposit")
            withdraw = event.content.get("Withdraw")
            carrier_balance = carrier_balance if isinstance(carrier_balance, int) else 0
            player_balance = player_balance if isinstance(player_balance, int) else 0
            deposit = deposit if isinstance(deposit, int) else 0
            withdraw = withdraw if isinstance(withdraw, int) else 0
            entry.Finance = {
                **entry.Finance,
                "CarrierBalance": carrier_balance,
                "PlayerBalance": player_balance,
                "Deposit": deposit,
                "Withdraw": withdraw,
            }

        if event_name == "CarrierDepositFuel":
            total = event.content.get("Total", entry.FuelLevel)
            if not isinstance(total, int):
                total = entry.FuelLevel
            entry.FuelLevel = total

        if event_name == "CarrierCrewServices":
            crew_role = event.content.get("CrewRole")
            if isinstance(crew_role, str) and crew_role:
                crew = next((c for c in entry.Crew if c.get("CrewRole") == crew_role), None)
                if crew is None:
                    crew = {"CrewRole": crew_role}
                    entry.Crew.append(crew)
                operation = event.content.get("Operation", "")
                if not isinstance(operation, str):
                    operation = ""
                if isinstance(crew, dict):
                    crew["Operation"] = operation
                if "CrewName" in event.content:
                    crew_name = event.content.get("CrewName", "")
                    if not isinstance(crew_name, str):
                        crew_name = ""
                    if isinstance(crew, dict):
                        crew["CrewName"] = crew_name

        if event_name == "CarrierFinance":
            carrier_balance = event.content.get("CarrierBalance")
            reserve_balance = event.content.get("ReserveBalance")
            available_balance = event.content.get("AvailableBalance")
            reserve_percent = event.content.get("ReservePercent")
            tax_repair = event.content.get("TaxRate_repair")
            tax_refuel = event.content.get("TaxRate_refuel")
            tax_rearm = event.content.get("TaxRate_rearm")
            carrier_balance = carrier_balance if isinstance(carrier_balance, int) else 0
            reserve_balance = reserve_balance if isinstance(reserve_balance, int) else 0
            available_balance = available_balance if isinstance(available_balance, int) else 0
            reserve_percent = reserve_percent if isinstance(reserve_percent, int) else 0
            tax_repair = tax_repair if isinstance(tax_repair, int) else 0
            tax_refuel = tax_refuel if isinstance(tax_refuel, int) else 0
            tax_rearm = tax_rearm if isinstance(tax_rearm, int) else 0
            entry.Finance = {
                **entry.Finance,
                "CarrierBalance": carrier_balance,
                "ReserveBalance": reserve_balance,
                "AvailableBalance": available_balance,
                "ReservePercent": reserve_percent,
                "TaxRate_repair": tax_repair,
                "TaxRate_refuel": tax_refuel,
                "TaxRate_rearm": tax_rearm,
            }

        if event_name == "CarrierTradeOrder":
            commodity = event.content.get("Commodity_Localised", event.content.get("Commodity", "Unknown"))
            if not isinstance(commodity, str):
                commodity = "Unknown"
            black_market = event.content.get("BlackMarket", False)
            if not isinstance(black_market, bool):
                black_market = False
            order_key = f"{commodity}:{'black' if black_market else 'legal'}"
            if event.content.get("CancelTrade"):
                entry.TradeOrders.pop(order_key, None)
            else:
                order_type = None
                order_amount = None
                if "PurchaseOrder" in event.content:
                    order_type = "Purchase"
                    order_amount = event.content.get("PurchaseOrder")
                elif "SaleOrder" in event.content:
                    order_type = "Sale"
                    order_amount = event.content.get("SaleOrder")
                if order_type is not None and not isinstance(order_amount, int):
                    order_amount = 0
                price_value = event.content.get("Price")
                timestamp_value = event.content.get("timestamp", entry.Timestamp)
                if not isinstance(price_value, int):
                    price_value = 0
                if not isinstance(timestamp_value, str):
                    timestamp_value = entry.Timestamp
                trade_order = {
                    "Commodity": commodity,
                    "BlackMarket": black_market,
                    "OrderType": order_type,
                    "OrderAmount": order_amount,
                    "Price": price_value,
                    "Timestamp": timestamp_value,
                }
                entry.TradeOrders[order_key] = trade_order

        if event_name == "CarrierJumpRequest":
            system_name = event.content.get("SystemName")
            body_name = event.content.get("Body")
            system_address = event.content.get("SystemAddress")
            body_id = event.content.get("BodyID")
            departure_time = event.content.get("DepartureTime")
            pending = CarrierJumpRequestItem(
                CarrierType=carrier_type,
                CarrierID=carrier_id,
                SystemName=system_name if isinstance(system_name, str) else "Unknown",
                Body=body_name if isinstance(body_name, str) else "Unknown",
                SystemAddress=system_address if isinstance(system_address, int) else 0,
                BodyID=body_id if isinstance(body_id, int) else 0,
                DepartureTime=departure_time if isinstance(departure_time, str) else "1970-01-01T00:00:00Z",
            )
            self.state.PendingJumps[carrier_id] = pending

            now_utc = datetime.now(timezone.utc)
            projected_events = self._process_jump_timers(now_utc)
            return projected_events if projected_events else None

        if event_name == "CarrierJumpCancelled":
            self.state.PendingJumps.pop(carrier_id, None)

        return None

    def process_timer(self) -> list[ProjectedEvent]:
        current_time = datetime.now(timezone.utc)
        return self._process_jump_timers(current_time)
