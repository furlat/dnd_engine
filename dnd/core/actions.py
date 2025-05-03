from pydantic import BaseModel, Field, ConfigDict
from dnd.core.events import Event, EventHandler, EventPhase, EventProcessor
from dnd.core.values import BaseObject
from typing import Optional, Dict, Callable, OrderedDict, List, Literal


CostType =  Literal["actions", "bonus_actions", "reactions", "movement"]

class Action(BaseObject):
    description: str  = Field(description="The description of the action, this is going to be displayed in the ui as a tooltip")
    parent_event: Optional[Event] = Field(description="The parent event of the action, the first event to be created in the action will be a child of this event used to keep track of sub-actions triggered by other events")
    prerequistes: OrderedDict[str,EventProcessor] = Field(description="A dictionary of prerequistes, the key is the name of the prerequiste and the value is a callable that returns a boolean")
    consequences: OrderedDict[str,EventProcessor] = Field(description="A dictionary of consequences, the key is the name of the consequence and the value is a callable that returns a Event, the event will be tunneleed through the ordered dict")
    revalidate_prerequistes: bool = Field(default=True,description="If true, the prerequistes will be revalidated when the event is applied")
    events: List[Event] = Field(default_factory=list,description="A list of events that are going to be created by the action")
    cost_type: CostType = Field(default="actions",description="The type of cost for the action")
    cost: int = Field(default=0,description="The cost of the action")
    cost_checker: Optional[EventProcessor] = Field(default=None,description="An event processor that will be used to check if the action has the resources to be applied")
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def _apply_handler(self,event: Event, event_handler: EventHandler) -> Optional[Event]:
        """ Apply the handler to the event """
        return event_handler(event)
    
    
    def check_prerequistes(self,event: Event) -> Event:
        """ Check the prerequistes used both by the application and standalone 
         with a dummy event used by the game engine for checking available actions for all the targets
          during application is mostly used to see if any reaction to the events in between prevalidation for the interface
           and actual application had some side effects that could change the prerequistes results """
        #first apply the cost checker
        if self.cost_checker is not None:
            cost_checker_event = self.cost_checker(event,event.source_entity_uuid)
            if cost_checker_event is None:
                return event.cancel(status_message=f"Cost checker failed")
            elif cost_checker_event.canceled:
                return cost_checker_event
        #then apply the prerequistes
        for prerequiste_name, prerequiste_function in self.prerequistes.items():
            prerequiste_event = prerequiste_function(event,event.source_entity_uuid)
            if prerequiste_event is None :
                return event.cancel(status_message=f"Prerequiste {prerequiste_name} failed")
            if prerequiste_event.canceled:
                return prerequiste_event
          
        return prerequiste_event
    

    def apply_consequences(self,event: Event) -> Optional[Event]:
        """ Apply the consequences in order to the event
         consequences should take events in either the execution or in the effect phase and return an event in the execution or effect phase respectively """
        application_event = event.phase_to(EventPhase.EXECUTION,status_message=f"Applying consequences for {self.name}")
        if application_event.canceled:
            return application_event
        for consequence_name, consequence_function in self.consequences.items():
            consequence_event = consequence_function(application_event,application_event.source_entity_uuid)
            if consequence_event is None:
                return application_event.cancel(status_message=f"Consequence {consequence_name} failed the event")
            elif consequence_event.canceled:
                return consequence_event
            else:
                if self.revalidate_prerequistes:
                    consequence_event = self.check_prerequistes(consequence_event)
                    if consequence_event.canceled:
                        return consequence_event
             
        final_event = consequence_event.phase_to(EventPhase.COMPLETION,status_message=f"Applying consequences for {self.name}")
        return final_event
    

    def _create_declaration_event(self,parent_event: Optional[Event] = None) -> Optional[Event]:
        """ to be overriden by subclasses to create a specific declaration event"""
        
        return None
    
    def create_declaration_event(self,parent_event: Optional[Event] = None) -> Event:
        """ Create the start event returns the output of the private method _create_declaration_event or defaults to a generic event
        it should not really be of any gameplay use to react to this declaration event, but it could be useful for gui or other interfaces"""
        declaration_event = self._create_declaration_event(parent_event)
        if declaration_event is None:
            return Event(name=f"{self.name} start",description=self.description,parent_event=parent_event, phase=EventPhase.DECLARATION)
        else:
            return declaration_event
    
    def apply(self,parent_event: Optional[Event] = None) -> Optional[Event]:
        """ Apply the action if the prerequistes are met 
        1) action gets declared
        2) pre_requisetes get checked """
        action_declaration_event = self.create_declaration_event(parent_event) 
        self.events.append(action_declaration_event)
        if action_declaration_event.canceled:
            return action_declaration_event
        prerequiste_event = self.check_prerequistes(action_declaration_event)
        if prerequiste_event.canceled:
            return prerequiste_event
        else:
            return self.apply_consequences(prerequiste_event)
