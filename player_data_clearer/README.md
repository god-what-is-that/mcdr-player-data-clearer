# mcdr-player-data-clearer
依赖uuid_api_remake插件。  
在配置文件中添加你需要删除的玩家数据位置以及后缀。默认会删除world/playerdata/uuid.dat+dat_old、advancements/uuid.json、stats/uuid.json。  
!!cpd uuid [uuid], 清除指定UUID的玩家数据。  
!!cpd playerid [playerid], 清除指定玩家数据。  
!!cpd clean [day]，清除多少天没修改的玩家数据。不是查的usercache.json，是直接查world的playerdata的修改日期。
