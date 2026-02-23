some notes on the items and intenvory plan:


1) ITEM CLASS HIEARCHY DESIGN: we could start by keeping an excplict separation between equippable items and usable items 

    I would starty with baseitem which can either be looted or not / has presence on the gridmap/interacts with senses // requires us to write the inventory but basically supports only looting (no using no equiping)
    here we handle the _loot _drop _destroy methods?  I am moving the _destroy here as a base hookup for both consumable and thigns that can be targeted/broken 
    the optional presence of a health block could start here. -- I personally do not care about AC for now and would focus on HP and in case we give damage reduction based on teh material? we said we are goingto give an attack object actioon to the entities as default action - so this is a 


    then we have 2 direct subclasses EquippabbleItem with the equip _equip / _remove setup ehere we can define the various type of wewapon slots/weapons 


    thne we have usable items at this point I like the idea of having live discovery of the actions and basically having a method in the item that returns the action template look good - this could be a trivial method simply returning a stored aciton template or adaptively modifying creating it based on the item/user state 

    the first usable items I would focus on are environment/not pickable items like levers and doors without an explicit target (mostly tageting self) - e.g it could be a lever that removes the dangerous terrain in the example arena 

    -- this creates a non ortogonal special separation all items are lootable/not lootable and have logics for their presence in teh map/inventory  then we separate between items that can be equipped (requires to be lootable obviously) and items that can be used 

    this means that items that can be equipped IF they give actions they use the pattern used in teh class system directly registering to user rather than giving a USE action.  
    I think both subclass and the equipment enum can exist in baseitem as they should only need BaseAction and BaseCondition so they can be imported in equipment as is now (instead of being define there) - maybe we do not need the subclasses for the items just them having the correct slot enum ? 
2) Blocks Organizaiton in Entity
    On simplificatory conseuqence is that we can think of equipment/inventory as separate blocks flat in the entity (i know we are gonna slop a bit entity with methods but for now I prefer this) - equip / remove are not responsible for where the item is going to end up that is going to be wrapped by the entity that can either conclude by dropping hte item on the floor or moving it to equipment. 

    The whole discussion about refactoring equipment combat stats etc is meaningful in teh sense that entity is becoming very heavy so we might want to have a proper study (future not now - we can make some example but this is not our current objective) on how can we create some metablocks [e.g. combat stats together with equipment / magic stats and inventory] that can encapsulate some logics without requiring the rest and move some of the entity methods to the blocks but for now let's keep the curent setup and ensure everything works this is indpendent reorganization once we have full understanding of the dependencies. 


3) Adherence to Rules: free object interaction/use cost etc I would delay this and have each action defines its cost in the same way that actions already do - we can have free actions actions costing bonus action and even actions costing custom resources -- I do not care at ALL about magic attunement that is just a silly logic we want to make full use of items - a item could have an action to "bind" it but that would be some custom logic probably working on _equip or something like that . Pick up/drop can be free actions. We can fully ignore encumbrance for nwo but I guess if items have a weight being able to keep track of the weight is a good thing.


4) Conditions: this is I think where it can get messy - we need to be sure not to mess up with the conditions setup - it is true that conditiosn only require a baseblock but right now we are handling most ofconditions applicaiton/removal/expiration through entities. We should study what can we move down to baseblock - if baseblock is possibly fully responsible for conditions management - conditions to others would be conditions to other baseblocks instead of entity and we can have the same sort of logic as we have now for effect on other to implement spells that target the object but depend on some condition. Same at the moment conditions can not directly progress on the item as the progress of the condition is handled by the entity and is turn based but at least we have this pattern - this is the most dubious part I have we might have to add an environment turn (at the end of all turns maybe?) for object conditions that do not depend on other entities?. Otherwise we need to create some logic for this and have entity handle the to items conditions separately from the to entity conditions. This could come helpeful also for tiles conditions since now they would both descend from block that has the methods. Remember we do not want to wrap everything in conditions if not needed we can have the _equip and _unequip handle a lot of stuff like actions and modifiers no need to squash everything in the condition system if they do not require it. 


5) movement blocking and vision blocking - this here we really have to think throughly your currently proposed methods give too much responsability to gridmap and you can see is wrong but the fact that you are using obj getattr - whenever you use the getattr pattern you are doing something awkard with the types hierarchi. Let's see if maybe base_block could have a method called blocks_walking blocks_vision that gets used? how do we have entity blocks navigation through their location right now? where does this happen? agin this methods could be conditional on the source entity that needs to see/move -- again if we move it down to baseblock then maybe senses has this type of information etc? we definetely need to separate then betwee nbaseblocks that are in the map vs those part of an entity/equipped/inventory but this is alraedy to be studied for how we have items that are on the ground/inventory. 

6) we can delay phase transitions like an objects getting destroyed e.g. wooden_wall --> rubbles or entity --> body to later but that is just a common framework for transitions from one entity to the other with some inherithed states/conditions etc - we probably e.g. for entity -->body we still want to keep the old entity object for e.g. resurrection 