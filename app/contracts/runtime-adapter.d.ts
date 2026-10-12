export type CommandName = 'scan_asset'|'register_pair'|'register_component'|'link_pair'|'verify_inventory'|'transfer_location';
export type QueryName = 'list_inventory'|'get_pair'|'find_asset'|'asset_history'|'runtime_status';
export interface Pair {pair_id:string;size_value:string;size_system:string;category:string;availability_state:string;current_location_id:string;custodian_org_id:string;version:number;}
export interface CommandEnvelope {command_id:string;schema_version:'0.1.0';command_name:CommandName;requested_at:string;actor_id:string;actor_role:string;device_id:string;location_id:string;idempotency_key:string;payload:Record<string,unknown>;offline_created:boolean;expected_pair_version?:number;}
export interface CommandReceipt {receipt_id:string;command_id:string;status:'ACCEPTED'|'DUPLICATE'|'CONFLICT'|'REJECTED';recorded_at:string;event_ids:string[];result:Record<string,any>;error:{code:string;message:string}|null;}
export interface RuntimeAdapter {connect():Promise<any>;submitCommand(envelope:CommandEnvelope):Promise<CommandReceipt>;readInventory():Promise<Pair[]>;readPair(pair_id:string):Promise<Pair|null>;health():Promise<any>;}
