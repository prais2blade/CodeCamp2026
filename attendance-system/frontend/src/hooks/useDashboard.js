import { useQuery } from "@tanstack/react-query";

import {
    getDashboardStats
} from "../api/dashboardApi";

export function useDashboard() {

    return useQuery({

        queryKey: [
            "dashboard"
        ],

        queryFn:
            getDashboardStats,

    });

}