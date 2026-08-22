package com.acme.demo.job;

import com.xxl.job.core.handler.annotation.XxlJob;
import com.acme.demo.app.OrderCreateCmdExe;

public class SyncJob {

    private final OrderCreateCmdExe orderCreateCmdExe;

    public SyncJob(OrderCreateCmdExe orderCreateCmdExe) {
        this.orderCreateCmdExe = orderCreateCmdExe;
    }

    @XxlJob("syncOrder")
    public void sync() {
        orderCreateCmdExe.execute();
    }
}
