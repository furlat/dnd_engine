//! Isolated API feasibility probe; this is not a dnd_engine implementation.
//!
//! Requested behavior: preserve synchronous event mutation, cancellation and
//! nested resolution, including reentry into the same mechanic.
//! Boundary: one caller invokes native Bevy systems and inspects the returned
//! event plus ECS state before issuing another command.
//! Inputs: a plate press with two output links; a shieldable attack; an ordered
//! three-handler event; a recursive registered system; two custom-trigger events.
//! Expected outputs are asserted in main. There is no App, renderer, Schedule,
//! frame advance, domain tick, continuation queue or external gameplay runtime.

use bevy_ecs::event::Trigger;
use bevy_ecs::observer::{CachedObservers, TriggerContext};
use bevy_ecs::prelude::*;
use bevy_ecs::system::{BoxedSystem, InMut, IntoSystem, RegisteredSystemError, RunSystemOnce, SystemId};
use bevy_ecs::world::DeferredWorld;
use std::time::Instant;

#[derive(Resource, Default)]
struct Trace(Vec<&'static str>);

#[derive(Component)]
struct Plate {
    pressed: bool,
    outputs: [OutputLink; 2],
}

#[derive(Clone, Copy)]
enum OutputLink {
    MoveOffPlate,
    SecondPulse,
}

#[derive(Component)]
struct Occupant {
    on_plate: bool,
}

#[derive(Component)]
struct TransferMarker;

#[derive(Resource, Default)]
struct Outputs {
    first: u32,
    second: u32,
}

#[derive(Clone, Copy)]
struct Contact {
    plate: Entity,
    occupant: Entity,
    use_cached_native_systems: bool,
}

struct LinkActivation {
    contact: Contact,
    link: OutputLink,
}

#[derive(Resource, Default)]
struct PressureExecutors {
    // These are Bevy System instances and their native parameter/query caches.
    // No persistent plate or encounter state belongs in this cache or Local.
    inactive: Vec<BoxedSystem<In<Contact>, ()>>,
    initialized: u32,
    reused: u32,
}

fn invoke_pressure(world: &mut World, contact: Contact) {
    if !contact.use_cached_native_systems {
        world.run_system_once_with(pressure_contact, contact).unwrap();
        return;
    }

    let inactive = world.resource_mut::<PressureExecutors>().inactive.pop();
    // Release the cache's resource borrow before invoking or initializing a
    // native System. Recursive calls can take another inactive instance, or
    // initialize one when every existing instance is active.
    let mut system = if let Some(system) = inactive {
        world.resource_mut::<PressureExecutors>().reused += 1;
        system
    } else {
        let mut system: BoxedSystem<In<Contact>, ()> =
            Box::new(IntoSystem::into_system(pressure_contact));
        system.initialize(world);
        world.resource_mut::<PressureExecutors>().initialized += 1;
        system
    };
    match system.run(contact, world) {
        Ok(()) => world.resource_mut::<PressureExecutors>().inactive.push(system),
        // A failed instance may retain unapplied Commands. Drop it rather than
        // placing dirty native parameter buffers back in the inactive cache.
        Err(error) => panic!("Pressure system failed: {error}"),
    }
}

// This is a native Bevy exclusive system with an owned Bevy input. Concurrently
// active invocations use distinct native System state; plate state is in the ECS.
fn pressure_contact(
    In(contact): In<Contact>,
    world: &mut World,
    occupant_query: &mut QueryState<&Occupant>,
) {
    let occupied = occupant_query.get(world, contact.occupant).unwrap().on_plate;
    let outputs = {
        let mut plate = world.get_mut::<Plate>(contact.plate).unwrap();
        if plate.pressed == occupied {
            return;
        }
        plate.pressed = occupied;
        // Preserve the source mechanic's original press decision and complete
        // authored output list even if output one recursively releases us.
        plate.outputs
    };
    world.resource_mut::<Trace>().0.push(if occupied {
        "press committed"
    } else {
        "release committed"
    });

    if occupied {
        for link in outputs {
            world
                .run_system_once_with(activate_link, LinkActivation { contact, link })
                .unwrap();
            // Resume the SAME outer native QueryState after nested execution
            // changed the occupant's archetype and reentered this mechanic.
            assert!(!occupant_query.get(world, contact.occupant).unwrap().on_plate);
        }
    }
    world.resource_mut::<Trace>().0.push(if occupied {
        "press completed"
    } else {
        "release completed"
    });
}

fn activate_link(In(activation): In<LinkActivation>, world: &mut World) {
    match activation.link {
        OutputLink::MoveOffPlate => {
            world.resource_mut::<Outputs>().first += 1;
            world.resource_mut::<Trace>().0.push("first output");
            world
                .get_mut::<Occupant>(activation.contact.occupant)
                .unwrap()
                .on_plate = false;
            // Force a real archetype move during nested resolution. This tests
            // native QueryState reuse after structural changes; the marker is
            // probe instrumentation, not an added pressure-plate rule.
            world.entity_mut(activation.contact.occupant).insert(TransferMarker);
            // Reenter EXACTLY the same pressure_contact native system function
            // synchronously while its original press invocation is active.
            invoke_pressure(world, activation.contact);
            assert!(!world.get::<Plate>(activation.contact.plate).unwrap().pressed);
            world.resource_mut::<Trace>().0.push("first output resumed");
        }
        OutputLink::SecondPulse => {
            assert!(!world.get::<Plate>(activation.contact.plate).unwrap().pressed);
            world.resource_mut::<Outputs>().second += 1;
            world.resource_mut::<Trace>().0.push("second output");
        }
    }
}

#[derive(Component)]
struct ActorResources {
    reactions: u8,
    spell_slots: u8,
}

#[derive(Component)]
struct ShieldBuff;

#[derive(Debug)]
struct Attack {
    target: Entity,
    hit: bool,
    canceled: bool,
    handlers: Vec<&'static str>,
}

// Native Bevy Query + Commands + In system, with a returned event value.
fn shield(
    In(mut attack): In<Attack>,
    mut actors: Query<&mut ActorResources>,
    mut commands: Commands,
) -> Attack {
    let mut resources = actors.get_mut(attack.target).unwrap();
    assert!(resources.reactions > 0 && resources.spell_slots > 0);
    resources.reactions -= 1;
    resources.spell_slots -= 1;
    attack.hit = false;
    attack.handlers.push("shield");
    commands.entity(attack.target).insert(ShieldBuff);
    attack
}

fn cancel_attack(In(mut attack): In<Attack>) -> Attack {
    attack.canceled = true;
    attack.handlers.push("cancel");
    attack
}

fn later_handler(In(mut attack): In<Attack>) -> Attack {
    attack.handlers.push("later");
    attack
}

fn in_place_no_replacement(
    (InMut(attack), In(owner)): (InMut<Attack>, In<Entity>),
    actors: Query<&ActorResources>,
) -> Option<Attack> {
    assert_eq!(attack.target, owner);
    assert_eq!(actors.get(owner).unwrap().reactions, 0);
    attack.hit = false;
    attack.handlers.push("mutate in place, return None");
    None
}

type AttackRuleSystem = BoxedSystem<In<Attack>, Attack>;

#[derive(Component)]
struct AttackRule {
    order: u32,
    make_system: fn() -> AttackRuleSystem,
}

fn make_shield() -> AttackRuleSystem {
    Box::new(IntoSystem::into_system(shield))
}

fn make_cancel() -> AttackRuleSystem {
    Box::new(IntoSystem::into_system(cancel_attack))
}

fn make_later() -> AttackRuleSystem {
    Box::new(IntoSystem::into_system(later_handler))
}

// This small domain dispatch loop preserves the existing ordered-handler rule.
// The actual handlers execute through Bevy's native System API, including its
// query validation, input/output handling and deferred command application.
fn ordered_handlers(In(mut attack): In<Attack>, world: &mut World) -> Attack {
    // Snapshot executable descriptors, not borrowed components, before running
    // any rule. Here the query stands in for the engine's existing trigger/cell
    // indexes; no claim is made that scanning all rules is a production strategy.
    let mut rules: Vec<_> = world
        .query::<&AttackRule>()
        .iter(world)
        .map(|rule| (rule.order, rule.make_system))
        .collect();
    rules.sort_by_key(|(order, _)| *order);
    for (order, make_system) in rules {
        let mut system = make_system();
        system.initialize(world);
        attack = system.run(attack, world).unwrap();
        if order == 0 {
            // Commands from shield have already applied before this caller
            // resumes; this was an actual structural component insertion.
            assert!(world.get::<ShieldBuff>(attack.target).is_some());
        }
        if attack.canceled {
            break;
        }
    }
    attack
}

#[derive(Resource)]
struct StoredRecursiveSystem(SystemId<In<u8>, bool>);

fn stored_recursion(In(depth): In<u8>, world: &mut World) -> bool {
    if depth == 0 {
        return true;
    }
    let id = world.resource::<StoredRecursiveSystem>().0;
    match world.run_system_with(id, depth - 1) {
        Err(RegisteredSystemError::SystemMissing(_)) => false,
        result => panic!("Expected active SystemId reentry to fail, got {result:?}"),
    }
}

#[derive(Component)]
struct CanonicalEventHeader {
    parent: Option<Entity>,
    children: Vec<Entity>,
}

#[derive(Component)]
struct CanonicalEventPayload {
    accepted_number: u32,
}

// This alternative canonical-history seam stores durable event data in native
// ECS components. Handlers receive an event handle; they do not keep a mutable
// event borrow across nested execution. It is separate from the InMut API proof.
fn canonical_parent(In(parent): In<Entity>, world: &mut World) -> Entity {
    {
        let mut payload = world.get_mut::<CanonicalEventPayload>(parent).unwrap();
        payload.accepted_number = 42;
    }
    let child = world.run_system_once_with(canonical_child, parent).unwrap();
    // Nested execution observed the edited parent and linked its child into the
    // same canonical parent record. The resumed caller sees that link now.
    assert_eq!(world.get::<CanonicalEventHeader>(parent).unwrap().children, [child]);
    assert_eq!(world.get::<CanonicalEventPayload>(child).unwrap().accepted_number, 43);
    child
}

fn canonical_child(In(parent): In<Entity>, world: &mut World) -> Entity {
    let parent_value = world.get::<CanonicalEventPayload>(parent).unwrap().accepted_number;
    assert_eq!(parent_value, 42);
    let child = world.spawn((
        CanonicalEventHeader { parent: Some(parent), children: Vec::new() },
        CanonicalEventPayload { accepted_number: parent_value + 1 },
    )).id();
    world.get_mut::<CanonicalEventHeader>(parent).unwrap().children.push(child);
    child
}

#[derive(Event)]
struct AdvanceBuiltinTriggerId;

#[derive(Event)]
struct ParentNotification;

#[derive(Event)]
struct ChildNotification;

#[derive(Default)]
struct CustomOrderedTrigger;

#[derive(Event, Default)]
#[event(trigger = CustomOrderedTrigger)]
struct CustomIntercept {
    observer_calls: u32,
}

// Deliberately reproduces upstream issue #21441. This is not proposed migration
// code. Custom Trigger cannot advance Bevy's private deduplication trigger id,
// so manually invoking standard observer runners skips repeated dispatches.
// SAFETY: the event's associated trigger is exactly Self; all runners and context
// come from this event's matching CachedObservers in this same DeferredWorld.
unsafe impl Trigger<CustomIntercept> for CustomOrderedTrigger {
    unsafe fn trigger(
        &mut self,
        mut world: DeferredWorld,
        observers: &CachedObservers,
        context: &TriggerContext,
        event: &mut CustomIntercept,
    ) {
        let mut ordered: Vec<_> = observers.global_observers().iter().collect();
        ordered.sort_by_key(|(observer, _)| observer.to_bits());
        for (observer, runner) in ordered {
            // SAFETY: see impl safety comment. The event and trigger have the
            // exact types expected by the associated observer runner.
            unsafe {
                runner(
                    world.reborrow(),
                    *observer,
                    context,
                    (&mut *event).into(),
                    (&mut *self).into(),
                );
            }
        }
    }
}

fn main() {
    let started = Instant::now();
    let mut world = World::new();
    world.init_resource::<Trace>();
    world.init_resource::<Outputs>();
    world.init_resource::<PressureExecutors>();
    let plate = world
        .spawn(Plate {
            pressed: false,
            outputs: [OutputLink::MoveOffPlate, OutputLink::SecondPulse],
        })
        .id();
    let occupant = world.spawn(Occupant { on_plate: true }).id();

    invoke_pressure(&mut world, Contact {
        plate, occupant, use_cached_native_systems: false,
    });

    assert!(!world.get::<Plate>(plate).unwrap().pressed);
    assert_eq!(world.resource::<Outputs>().first, 1);
    assert_eq!(world.resource::<Outputs>().second, 1);
    assert_eq!(
        world.resource::<Trace>().0,
        [
            "press committed",
            "first output",
            "release committed",
            "release completed",
            "first output resumed",
            "second output",
            "press completed",
        ]
    );
    println!("same-rule synchronous reentry: {:?}", world.resource::<Trace>().0);

    world.resource_mut::<Trace>().0.clear();
    world.entity_mut(occupant).remove::<TransferMarker>();
    let cached_contact = Contact {
        plate, occupant, use_cached_native_systems: true,
    };
    for outer_call in 1..=2 {
        world.get_mut::<Occupant>(occupant).unwrap().on_plate = true;
        invoke_pressure(&mut world, cached_contact);
        assert!(!world.get::<Plate>(plate).unwrap().pressed);
        assert_eq!(world.resource::<PressureExecutors>().initialized, 2);
        assert_eq!(world.resource::<PressureExecutors>().inactive.len(), 2);
        assert_eq!(world.resource::<Outputs>().first, outer_call + 1);
        assert_eq!(world.resource::<Outputs>().second, outer_call + 1);
    }
    assert_eq!(world.resource::<PressureExecutors>().reused, 2);
    let expected_one_press = [
        "press committed", "first output", "release committed", "release completed",
        "first output resumed", "second output", "press completed",
    ];
    assert_eq!(world.resource::<Trace>().0, expected_one_press.repeat(2));
    println!(
        "cached native systems: initialized={}, reused={}, inactive={} after two recursive outer calls",
        world.resource::<PressureExecutors>().initialized,
        world.resource::<PressureExecutors>().reused,
        world.resource::<PressureExecutors>().inactive.len(),
    );

    let actor = world
        .spawn(ActorResources { reactions: 1, spell_slots: 1 })
        .id();
    world.spawn(AttackRule { order: 2, make_system: make_later });
    world.spawn(AttackRule { order: 0, make_system: make_shield });
    world.spawn(AttackRule { order: 1, make_system: make_cancel });
    let attack = world
        .run_system_once_with(
            ordered_handlers,
            Attack { target: actor, hit: true, canceled: false, handlers: Vec::new() },
        )
        .unwrap();
    assert_eq!(attack.handlers, ["shield", "cancel"]);
    assert!(!attack.hit && attack.canceled);
    assert!(world.get::<ShieldBuff>(actor).is_some());
    assert_eq!(world.get::<ActorResources>(actor).unwrap().reactions, 0);
    assert_eq!(world.get::<ActorResources>(actor).unwrap().spell_slots, 0);
    println!("native Query + In mutation, structural buff and cancellation: {attack:?}");

    let mut borrowed_attack = Attack {
        target: actor, hit: true, canceled: false, handlers: Vec::new(),
    };
    let mut in_place_system: BoxedSystem<
        (InMut<'static, Attack>, In<Entity>), Option<Attack>,
    > = Box::new(IntoSystem::into_system(in_place_no_replacement));
    in_place_system.initialize(&mut world);
    let replacement = in_place_system.run((&mut borrowed_attack, actor), &mut world).unwrap();
    assert!(replacement.is_none());
    assert!(!borrowed_attack.hit);
    assert_eq!(borrowed_attack.handlers, ["mutate in place, return None"]);
    println!("native tuple InMut + In preserves in-place change with no replacement: {borrowed_attack:?}");

    let canonical_parent_entity = world.spawn((
        CanonicalEventHeader { parent: None, children: Vec::new() },
        CanonicalEventPayload { accepted_number: 0 },
    )).id();
    let canonical_child_entity = world
        .run_system_once_with(canonical_parent, canonical_parent_entity)
        .unwrap();
    assert_eq!(
        world.get::<CanonicalEventHeader>(canonical_child_entity).unwrap().parent,
        Some(canonical_parent_entity),
    );
    assert_eq!(
        world.get::<CanonicalEventPayload>(canonical_parent_entity).unwrap().accepted_number,
        42,
    );
    println!("canonical live event history: nested child saw edited parent=42; parent sees linked child=43 before resuming");

    let id = world.register_system(stored_recursion);
    world.insert_resource(StoredRecursiveSystem(id));
    assert!(!world.run_system_with(id, 1).unwrap());
    println!("same active registered SystemId: SystemMissing, as expected");

    let mut notification_world = World::new();
    notification_world.init_resource::<Trace>();
    notification_world.add_observer(
        |_: On<ParentNotification>, mut trace: ResMut<Trace>, mut commands: Commands| {
            trace.0.push("parent before child enqueue");
            commands.trigger(ChildNotification);
            trace.0.push("parent after child enqueue");
        },
    );
    notification_world.add_observer(|_: On<ChildNotification>, mut trace: ResMut<Trace>| {
        trace.0.push("child resolved");
    });
    notification_world.trigger(ParentNotification);
    assert_eq!(
        notification_world.resource::<Trace>().0,
        ["parent before child enqueue", "parent after child enqueue"]
    );
    notification_world.flush();
    assert_eq!(
        notification_world.resource::<Trace>().0,
        [
            "parent before child enqueue",
            "parent after child enqueue",
            "child resolved",
        ]
    );
    println!("ordinary observer child timing: {:?}", notification_world.resource::<Trace>().0);

    let mut observer_world = World::new();
    observer_world.add_observer(|_: On<AdvanceBuiltinTriggerId>| {});
    observer_world.add_observer(|mut event: On<CustomIntercept>| event.observer_calls += 1);
    observer_world.trigger(AdvanceBuiltinTriggerId);
    let mut first = CustomIntercept::default();
    let mut second = CustomIntercept::default();
    observer_world.trigger_ref(&mut first);
    observer_world.trigger_ref(&mut second);
    assert_eq!(first.observer_calls, 1);
    assert_eq!(second.observer_calls, 0);
    println!("custom Trigger/default runner gap: first={}, second={}", first.observer_calls, second.observer_calls);
    println!("all mechanism assertions passed in {:?} (not a gameplay benchmark)", started.elapsed());
}
