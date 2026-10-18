//! Diagnostic for native queued execution, not a Fireball rules implementation.
//! Input: three damage applications plus two compatible lighting invalidations.
//! Output: bounded Pending/Complete receipts and committed health/light/sight.
use bevy_ecs::{prelude::*, system::RunSystemOnce};
use std::collections::VecDeque;

#[derive(Component)]
struct Health(i32);
#[derive(Component)]
struct Wall;
#[derive(Component)]
struct Broken;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct ApplicationId(u64);
#[derive(Clone, Copy)]
struct Damage {
    id: ApplicationId,
    target: Entity,
    amount: i32,
}
#[derive(Resource, Default)]
struct DamageQueue(VecDeque<Damage>);
#[derive(Resource, Default)]
struct BreakQueue(VecDeque<Entity>);
#[derive(Resource, Default)]
struct LightQueue(VecDeque<u64>);
#[derive(Resource, Default)]
struct SenseQueue(VecDeque<u64>);
#[derive(Resource, Default)]
struct Budget(usize);
#[derive(Resource, Default)]
struct Root {
    id: u64,
    pending: usize,
    applied: Vec<ApplicationId>,
}
#[derive(Resource, Default, Debug, PartialEq, Eq, Clone)]
struct Scene {
    light_revision: u64,
    light_level: u8,
    sight_revision: u64,
    visible_through_wall: bool,
}

// Coalescing is scoped to this root and one diagnostic lighting region.
// Production invalidations also need their actual region/revision dependencies.
fn dirty_light(queue: &mut LightQueue, root: &mut Root) {
    if !queue.0.contains(&root.id) {
        queue.0.push_back(root.id);
        root.pending += 1;
    }
}

fn produce_fireball(
    In(targets): In<[Entity; 3]>,
    mut damage: ResMut<DamageQueue>,
    mut lighting: ResMut<LightQueue>,
    mut root: ResMut<Root>,
) {
    root.id = 7;
    for (index, target) in targets.into_iter().enumerate() {
        damage.0.push_back(Damage {
            id: ApplicationId(70 + index as u64),
            target,
            amount: 4,
        });
        root.pending += 1;
    }
    dirty_light(&mut lighting, &mut root);
    dirty_light(&mut lighting, &mut root);
}

fn apply_damage(
    mut queue: ResMut<DamageQueue>,
    mut breaks: ResMut<BreakQueue>,
    mut root: ResMut<Root>,
    mut budget: ResMut<Budget>,
    mut health: Query<(&mut Health, Has<Wall>)>,
) {
    while budget.0 > 0 {
        let Some(job) = queue.0.pop_front() else { break };
        budget.0 -= 1;
        let (mut hp, wall) = health.get_mut(job.target).unwrap();
        let was_alive = hp.0 > 0;
        hp.0 = (hp.0 - job.amount).max(0);
        if wall && was_alive && hp.0 == 0 {
            breaks.0.push_back(job.target);
            root.pending += 1;
        }
        root.applied.push(job.id);
        root.pending -= 1;
    }
}

fn apply_breakage(
    mut queue: ResMut<BreakQueue>,
    mut lighting: ResMut<LightQueue>,
    mut root: ResMut<Root>,
    mut budget: ResMut<Budget>,
    mut commands: Commands,
) {
    while budget.0 > 0 {
        let Some(entity) = queue.0.pop_front() else { break };
        budget.0 -= 1;
        commands.entity(entity).insert(Broken);
        dirty_light(&mut lighting, &mut root);
        root.pending -= 1;
    }
}

fn update_lighting(
    mut queue: ResMut<LightQueue>,
    mut senses: ResMut<SenseQueue>,
    mut root: ResMut<Root>,
    mut budget: ResMut<Budget>,
    mut scene: ResMut<Scene>,
    walls: Query<Has<Broken>, With<Wall>>,
) {
    while budget.0 > 0 {
        let Some(root_id) = queue.0.pop_front() else { break };
        budget.0 -= 1;
        assert_eq!(root_id, root.id);
        scene.light_revision += 1;
        scene.light_level = if walls.single().unwrap() { 9 } else { 2 };
        senses.0.push_back(root_id);
        root.pending += 1;
        root.pending -= 1;
    }
}

fn update_senses(
    mut queue: ResMut<SenseQueue>,
    mut root: ResMut<Root>,
    mut budget: ResMut<Budget>,
    mut scene: ResMut<Scene>,
) {
    while budget.0 > 0 {
        let Some(root_id) = queue.0.pop_front() else { break };
        budget.0 -= 1;
        assert_eq!(root_id, root.id);
        scene.sight_revision = scene.light_revision;
        scene.visible_through_wall = scene.light_level >= 5;
        root.pending -= 1;
    }
}

#[derive(Debug, PartialEq, Eq)]
enum Receipt {
    Pending(u64),
    Complete(u64),
}
fn pump(world: &mut World, schedule: &mut Schedule, records: usize) -> Receipt {
    world.resource_mut::<Budget>().0 = records;
    schedule.run(world);
    let root = world.resource::<Root>();
    if root.pending == 0 { Receipt::Complete(root.id) }
    else { Receipt::Pending(root.id) }
}

fn main() {
    let mut world = World::new();
    world.init_resource::<DamageQueue>();
    world.init_resource::<BreakQueue>();
    world.init_resource::<LightQueue>();
    world.init_resource::<SenseQueue>();
    world.init_resource::<Budget>();
    world.init_resource::<Root>();
    world.init_resource::<Scene>();
    let a = world.spawn(Health(12)).id();
    let b = world.spawn(Health(9)).id();
    let wall = world.spawn((Health(4), Wall)).id();
    world.run_system_once_with(produce_fireball, [a, b, wall]).unwrap();
    // Producer admission returns before any child system runs or health changes.
    assert_eq!(world.get::<Health>(a).unwrap().0, 12);
    assert_eq!(world.get::<Health>(b).unwrap().0, 9);
    assert_eq!(world.get::<Health>(wall).unwrap().0, 4);
    assert_eq!(world.resource::<DamageQueue>().0.len(), 3);
    assert_eq!(world.resource::<LightQueue>().0.len(), 1);
    assert_eq!(world.resource::<Root>().pending, 4);
    let mut schedule = Schedule::default();
    schedule.add_systems((
        apply_damage, apply_breakage, ApplyDeferred, update_lighting, update_senses,
    ).chain());
    assert_eq!(pump(&mut world, &mut schedule, 1), Receipt::Pending(7));
    assert_eq!(world.get::<Health>(a).unwrap().0, 8);
    assert_eq!(world.get::<Health>(b).unwrap().0, 9);
    assert_eq!(world.resource::<Scene>().light_revision, 0);
    let mut passes = 1;
    while pump(&mut world, &mut schedule, 2) != Receipt::Complete(7) {
        passes += 1;
        assert!(passes < 10, "diagnostic cascade did not settle");
    }
    passes += 1;
    assert_eq!(world.get::<Health>(a).unwrap().0, 8);
    assert_eq!(world.get::<Health>(b).unwrap().0, 5);
    assert_eq!(world.get::<Health>(wall).unwrap().0, 0);
    assert!(world.get::<Broken>(wall).is_some());
    assert_eq!(world.resource::<Root>().applied,
        [ApplicationId(70), ApplicationId(71), ApplicationId(72)]);
    let settled = world.resource::<Scene>().clone();
    assert_eq!(settled, Scene {
        light_revision: 1, light_level: 9, sight_revision: 1,
        visible_through_wall: true,
    });
    assert_eq!(pump(&mut world, &mut schedule, 2), Receipt::Complete(7));
    assert_eq!(*world.resource::<Scene>(), settled);
    assert_eq!(world.resource::<Root>().applied.len(), 3);
    println!("queued native cascade passed in {passes} bounded pumps: health=[8,5,0], \
        applications=[70,71,72], {settled:?}; settled rerun unchanged");
}
