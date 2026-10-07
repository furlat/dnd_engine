// Installed package only. The script makes choices; all legality stays native.
import {randomUUID} from 'node:crypto';
import {mkdir,writeFile} from 'node:fs/promises';
import {connect,attach,status,choices,preview,submitCommand,receipt,createFollower,follow,waitForCursor} from '@neurodragon/player-sdk';
const sleep = ms => new Promise(resolve=>setTimeout(resolve,ms));
let connection = await connect(process.env.PLAYER_URL,process.env.PLAYER_TOKEN);
while (!connection.bootstrap.status.published_cursor) {await sleep(50); connection=await connect(process.env.PLAYER_URL,process.env.PLAYER_TOKEN);}
await attach(connection,{acquisition_id:randomUUID(),expected_attachment_epoch:connection.bootstrap.status.attachment_epoch});
const output=process.env.PLAYER_OUTPUT; await mkdir(output,{recursive:true});
let records=0,bytes=0,commands=0;
const follower=createFollower(connection,async(packet,raw)=>{
 bytes+=raw.byteLength;if(bytes>128*1024*1024)throw new Error('Acceptance recording quota exceeded');
 await writeFile(output+'/'+String(packet.cursor.sequence).padStart(6,'0')+'.json',raw);records++;
});
const abort=new AbortController();let done=false,error;
const task=follow(follower,{signal:abort.signal}).then(()=>{done=true},e=>{done=true;error=e});
const deadline=Date.now()+120000;
try {
 while(!done){
  if(Date.now()>deadline)throw new Error('Encounter deadline exceeded');
  let current=await status(connection);
  if(current.published_cursor)await waitForCursor(follower,current.published_cursor);
  const actor=current.boundary.input_actor_uuid;
  if(!actor||current.boundary.lifecycle!=='waiting_for_human'||!current.acknowledged_cursor||current.acknowledged_cursor.sequence<current.catch_up_cursor.sequence){await sleep(20);continue;}
  const revision=current.boundary.state_revision;
  const discovered=await choices(connection,{actor_uuid:actor,state_revision:revision,force_attack:false,correlation_id:randomUUID()});
  const available=discovered.choices;
  let row=available.entity_actions.find(row=>row.performs_attack&&row.can_afford&&row.valid_targets.length);
  if(!row){
   const movement=available.position_actions.find(row=>row.behavior_id==='action.move'&&row.can_afford&&row.valid_targets.length);
   if(movement){const target=[...movement.valid_targets].sort((a,b)=>(Math.abs(a.position[0]-7)+Math.abs(a.position[1]-7))-(Math.abs(b.position[0]-7)+Math.abs(b.position[1]-7)))[0];row={...movement,valid_targets:[target]};}
  }
  let intent={kind:'end_turn'};
  if(row){
   const selection={action_index:row.discovery_index,target_indices:[row.valid_targets[0].index],extra_target_positions:[]};
   const result=await preview(connection,{actor_uuid:actor,state_revision:revision,discovery_generation:available.discovery_generation,correlation_id:randomUUID(),selection});
   if(!result.preview.can_confirm)throw new Error('Single weapon target did not complete selection');
   intent={kind:'execute_selection',discovery_generation:available.discovery_generation,selection};
  }
  const command={command_number:current.next_command_number,actor_uuid:actor,state_revision:revision,intent};
  let result=await submitCommand(connection,command);await submitCommand(connection,command);
  while(result.receipt.kind==='pending'){await sleep(10);result=await receipt(connection,command.command_number);}
  if(result.receipt.kind!=='committed')throw new Error(JSON.stringify(result));
  await waitForCursor(follower,result.receipt.cursor);commands++;
  if(commands>80)throw new Error('Encounter did not terminate');
 }
 await task;if(error)throw error;
 await writeFile(output+'/result.json',JSON.stringify({language:'typescript',commands,records,bytes,final_cursor:follower.consumed,terminal:follower.completed}));
} finally {abort.abort();await task;}
