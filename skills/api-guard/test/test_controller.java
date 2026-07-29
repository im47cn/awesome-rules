package com.example.controller;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/logistics/v1/waybill")
public class TestWaybillController {

    @PostMapping("/create")
    public Result createWaybill(@RequestBody WaybillDTO dto) {
        return Result.success();
    }

    @GetMapping("/query")
    public Result queryWaybill(@RequestParam String orderNo) {
        return Result.success();
    }

    @PostMapping("/syncWaybill")
    public Result syncWaybill(@RequestBody SyncDTO dto) {
        return Result.success();
    }

    @PostMapping("/cancel/{id}")
    public Result cancelWaybill(@PathVariable Long id) {
        return Result.success();
    }

    @DeleteMapping("/delete")
    public Result deleteWaybill(@RequestBody DeleteDTO dto) {
        return Result.success();
    }

    @PostMapping("/receive")
    public Result receiveWaybill(@RequestBody ReceiveDTO dto) {
        return Result.success();
    }
}
